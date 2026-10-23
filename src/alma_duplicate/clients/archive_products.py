"""Bounded DataLink discovery; product URLs and service descriptors are not followed."""
from dataclasses import dataclass, replace
from hashlib import sha256
from http.client import HTTPException
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.domain.archive_products import ArchiveProduct, ProductDiscovery

MAX_RESPONSE_BYTES = 2_000_000
_UID = re.compile(r'uid://A[0-9A-Za-z]+/[0-9A-Za-z]+/[0-9A-Za-z]+')
_NS = '{http://www.ivoa.net/xml/VOTable/v1.3}'


def _identifiers(member, asdm):
    if not isinstance(member, str) or not _UID.fullmatch(member):
        raise ValueError('Invalid Member UID')
    if asdm is not None and (not isinstance(asdm, str) or not _UID.fullmatch(asdm)):
        raise ValueError('Invalid ASDM UID')


def parse_archive_products(raw: bytes, *, member_ous_uid: str,
                           asdm_uid: str | None = None) -> ProductDiscovery:
    """Read TABLEDATA links for one Member; requested ASDM remains unverified scope."""
    _identifiers(member_ous_uid, asdm_uid)
    metadata = dict(member_ous_uid=member_ous_uid, requested_asdm_uid=asdm_uid,
                    response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw))

    def failed(reason):
        return ProductDiscovery(**metadata, status='INVALID_RESPONSE', issues=(reason,))

    if len(raw) > MAX_RESPONSE_BYTES:
        return failed('RESPONSE_TOO_LARGE')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        return failed('XML_DECLARATIONS_UNSUPPORTED')
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, LookupError, ValueError):
        return failed('MALFORMED_XML')
    if root.tag != _NS + 'VOTABLE':
        return failed('UNSUPPORTED_VOTABLE_NAMESPACE')
    resources = [r for r in root.findall(_NS + 'RESOURCE') if r.get('type') == 'results']
    if len(resources) != 1:
        return failed('AMBIGUOUS_RESULTS_RESOURCE')
    resource = resources[0]
    if any(info.get('value') != 'OK' for info in resource.findall(_NS + 'INFO')
           if info.get('name') == 'QUERY_STATUS'):
        return failed('UNSUCCESSFUL_QUERY_STATUS')
    tables = resource.findall(_NS + 'TABLE')
    if len(tables) != 1:
        return failed('AMBIGUOUS_LINK_TABLE')
    table = tables[0]
    names = [f.get('name') for f in table.findall(_NS + 'FIELD')]
    required = {'ID', 'access_url', 'service_def', 'error_message', 'semantics',
                'description', 'content_type', 'content_length'}
    if not required.issubset(names) or len(set(names)) != len(names):
        return failed('INVALID_COLUMNS')
    data = table.findall(_NS + 'DATA')
    if len(data) != 1 or len(data[0]) != 1 or data[0][0].tag != _NS + 'TABLEDATA':
        return failed('UNSUPPORTED_TABLE_ENCODING')
    rows = data[0][0]
    products, issues = [], []
    for index, tr in enumerate(rows):
        if tr.tag != _NS + 'TR' or any(td.tag != _NS + 'TD' for td in tr):
            return failed('INVALID_TABLE_ROW')
        cells = [''.join(td.itertext()).strip() for td in tr]
        if len(cells) != len(names):
            return failed('ROW_COLUMN_COUNT_MISMATCH')
        row = dict(zip(names, cells))
        if row['ID'] != member_ous_uid:
            return failed('MEMBER_ID_MISMATCH')
        row_issues = []
        if row['error_message']:
            row_issues.append('DATALINK_ROW_ERROR')
        url = row['access_url'] or None
        service = row['service_def'] or None
        if url:
            try:
                parsed = urlsplit(url)
                valid = (parsed.scheme == 'https' and parsed.hostname
                         and parsed.username is None and parsed.password is None
                         and not any(c.isspace() for c in url))
            except ValueError:
                valid = False
            if not valid:
                row_issues.append('UNSUPPORTED_ACCESS_URL')
        if not url and not service and not row['error_message']:
            row_issues.append('MISSING_ACCESS_ROUTE')
        length = None
        if row['content_length']:
            if not row['content_length'].isascii() or not row['content_length'].isdigit():
                return failed('INVALID_CONTENT_LENGTH')
            length = int(row['content_length'])
        semantics = row['semantics']
        # These roles are declared by DataLink, not evidence of listobs contents.
        kind = {'#auxiliary': 'AUXILIARY_CANDIDATE', '#documentation': 'DOCUMENTATION',
                '#progenitor': 'PROGENITOR', '#this': 'DATASET'}.get(semantics, 'OTHER')
        if service and not url:
            kind = 'SERVICE_REFERENCE'
        if row['error_message']:
            kind = 'ERROR'
        if row.get('link_authorized', '').lower() in ('false', '0'):
            row_issues.append('ACCESS_REPORTED_UNAUTHORIZED')
        products.append(ArchiveProduct(
            index, member_ous_uid, url, service, semantics, row['description'],
            row['content_type'], length, row.get('link_auth') or None,
            row.get('link_authorized') or None, kind, tuple(row_issues),
        ))
        issues.extend(row_issues)
    status = 'DISCOVERED_WITH_ISSUES' if issues else 'DISCOVERED' if products else 'EMPTY'
    return ProductDiscovery(**metadata, status=status, products=tuple(products),
                            issues=tuple(dict.fromkeys(issues)))


@dataclass(frozen=True, slots=True)
class MetadataResponse:
    status_code: int
    body: bytes


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url):
    request = Request(url, headers={'Accept': 'application/x-votable+xml'})
    try:
        with build_opener(_NoRedirect).open(request, timeout=30) as response:
            return MetadataResponse(response.status, response.read(MAX_RESPONSE_BYTES + 1))
    except HTTPError as exc:
        with exc:
            return MetadataResponse(exc.code, exc.read(MAX_RESPONSE_BYTES + 1))


def discover_archive_products(member_ous_uid: str, *, asdm_uid: str | None = None,
                              origin: str = ARCHIVE_ORIGINS[0], fetch=None):
    """Return discovery, captured response bytes, and requested URL.

    Transport may be injected for deterministic tests. No product downloads,
    authentication, retries, or automatic mirror fallback occur here.
    """
    _identifiers(member_ous_uid, asdm_uid)
    if origin not in ARCHIVE_ORIGINS:
        raise ValueError('Select an official Archive origin')
    url = origin + '/datalink/sync?' + urlencode({'ID': member_ous_uid})
    try:
        response = (fetch or _fetch)(url)
    except (URLError, OSError, HTTPException):
        return (ProductDiscovery(member_ous_uid, asdm_uid, 'REQUEST_FAILED',
                                 issues=('METADATA_REQUEST_FAILED',)), None, url)
    raw = response.body
    if len(raw) > MAX_RESPONSE_BYTES or response.status_code != 200:
        reason = ('RESPONSE_TOO_LARGE' if len(raw) > MAX_RESPONSE_BYTES
                  else f'HTTP_{response.status_code}')
        status = 'ACCESS_DENIED' if response.status_code in (401, 403) else 'REQUEST_FAILED'
        result = ProductDiscovery(member_ous_uid, asdm_uid, status, issues=(reason,),
                                  response_sha256=sha256(raw).hexdigest(), response_bytes=len(raw))
    else:
        result = parse_archive_products(raw, member_ous_uid=member_ous_uid, asdm_uid=asdm_uid)
    return replace(result, http_status=response.status_code), raw, url
