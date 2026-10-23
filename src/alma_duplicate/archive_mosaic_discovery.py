"""Bounded TAP inventory capture for publicly visible science Mosaic executions."""
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.archive_mosaic_pipeline import MAX_METADATA_BYTES, read_mosaic_rows

MAX_ROWS = 10000


def inventory_request(member: str, source: str, origin=ARCHIVE_ORIGINS[0]) -> dict:
    """Construct a fixed query without TOP or an ASDM restriction."""
    if not isinstance(member, str) or not re.fullmatch(r'uid://A[0-9A-Za-z]+/[0-9A-Za-z]+/[0-9A-Za-z]+', member):
        raise ValueError('Invalid Member UID')
    if (not isinstance(source, str) or not source.strip() or source != source.strip()
            or len(source) > 256 or any(ord(c) < 32 for c in source)):
        raise ValueError('Invalid target name')
    if origin not in ARCHIVE_ORIGINS:
        raise ValueError('Select an official Archive origin')
    literal = source.replace("'", "''")
    query = ("SELECT DISTINCT proposal_id, member_ous_uid, asdm_uid, target_name, "
             "science_observation, is_mosaic FROM ivoa.obscore "
             f"WHERE member_ous_uid='{member}' AND target_name='{literal}' "
             "AND science_observation='T' AND is_mosaic='T'")
    params = dict(REQUEST='doQuery', LANG='ADQL', FORMAT='votable', MAXREC=str(MAX_ROWS), QUERY=query)
    return dict(member_ous_uid=member, source_name=source, origin=origin, query=query,
                maxrec=MAX_ROWS, url=origin + '/tap/sync?' + urlencode(params))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(url):
    try:
        with build_opener(_NoRedirect).open(Request(url, headers={'Accept': 'application/x-votable+xml'}), timeout=30) as response:
            return response.status, response.read(MAX_METADATA_BYTES + 1)
    except HTTPError as exc:
        with exc:
            return exc.code, exc.read(MAX_METADATA_BYTES + 1)


def _validate_rows(raw, request):
    rows = read_mosaic_rows(raw)
    # Conservatively reject a response at the limit even if its status says OK.
    if len(rows) >= MAX_ROWS:
        raise ValueError('Inventory reached MAXREC; completeness is unverified')
    if any(r['member_ous_uid'] != request['member_ous_uid'] or
           r['target_name'] != request['source_name'] for r in rows):
        raise ValueError('Inventory identity differs from request')
    if len({r['proposal_id'] for r in rows}) > 1:
        raise ValueError('Conflicting project identities')
    return rows


def capture_inventory(output: Path, *, member: str, source: str,
                      origin=ARCHIVE_ORIGINS[0], fetch=None):
    """Save request/response evidence, including failures; never overwrite a run."""
    request = inventory_request(member, source, origin)
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema_version='archive_mosaic_inventory_capture_1', request=request,
                   started_at=datetime.now(timezone.utc).isoformat(), status='REQUEST_FAILED')
    try:
        code, raw = (fetch or _fetch)(request['url'])
        raw = raw[:MAX_METADATA_BYTES + 1]
        (output / 'metadata.xml').write_bytes(raw)
        receipt.update(http_status=code, response_bytes=len(raw), response_sha256=sha256(raw).hexdigest())
        if code != 200:
            receipt.update(status='ACCESS_DENIED' if code in (401, 403) else 'REQUEST_FAILED', error=f'HTTP_{code}')
        else:
            receipt['status'] = 'INVALID_RESPONSE'
            rows = _validate_rows(raw, request)
            receipt.update(status='CAPTURED' if rows else 'EMPTY', row_count=len(rows),
                           asdm_uids=sorted({r['asdm_uid'] for r in rows}))
    except (OSError, HTTPException, ValueError, ET.ParseError) as exc:
        receipt['error'] = str(exc)
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    (output / 'inventory_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def verify_inventory_capture(raw: bytes, receipt_path: Path, *, member: str, source: str):
    """Verify local capture consistency, not remote authenticity or private coverage."""
    receipt = json.loads(receipt_path.read_bytes())
    request = receipt['request']
    if (receipt.get('schema_version') != 'archive_mosaic_inventory_capture_1'
            or request != inventory_request(member, source, request['origin'])
            or receipt.get('status') != 'CAPTURED' or receipt.get('http_status') != 200
            or receipt.get('response_bytes') != len(raw)
            or receipt.get('response_sha256') != sha256(raw).hexdigest()):
        raise ValueError('Inventory capture evidence mismatch')
    rows = _validate_rows(raw, request)
    if (not rows or receipt.get('row_count') != len(rows)
            or receipt.get('asdm_uids') != sorted({r['asdm_uid'] for r in rows})):
        raise ValueError('Inventory capture row summary mismatch')
    return receipt
