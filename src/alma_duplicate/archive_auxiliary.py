"""Receipt-bound auxiliary acquisition and bounded listobs inspection."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPException
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.clients.archive_products import _NoRedirect, parse_archive_products
from alma_duplicate.parsers.archive_listobs import parse_science_fields

MAX_DOWNLOAD = 300_000_000
MAX_EXPANDED = 1_000_000_000
MAX_MEMBER = 100_000_000
MAX_WEBLOG = 250_000_000
MAX_TEXT = 5_000_000
MAX_ENTRIES = 20000
MAX_CANDIDATES = 100
MAX_DEPTH = 2


def select_auxiliary(receipt: Path, row_index: int):
    """Reparse captured bytes; never trust serialized product URLs alone."""
    if type(row_index) is not int or row_index < 0:
        raise ValueError('Invalid product row index')
    receipt_bytes = receipt.read_bytes()
    saved = json.loads(receipt_bytes)
    if saved.get('schema_version') != 'archive_product_discovery_1' or saved.get('capture_truncated'):
        raise ValueError('Unsupported or truncated discovery receipt')
    if saved.get('response_file') != 'response.xml':
        raise ValueError('Expected response.xml beside discovery receipt')
    raw = (receipt.parent / 'response.xml').read_bytes()
    metadata = saved['discovery']
    if sha256(raw).hexdigest() != metadata['response_sha256'] or len(raw) != metadata['response_bytes']:
        raise ValueError('Discovery response integrity mismatch')
    parsed = parse_archive_products(raw, member_ous_uid=metadata['member_ous_uid'],
                                    asdm_uid=metadata['requested_asdm_uid'])
    if parsed.status not in ('DISCOVERED', 'DISCOVERED_WITH_ISSUES'):
        raise ValueError('Invalid discovery response')
    if row_index >= len(parsed.products):
        raise ValueError('Product row does not exist')
    product = parsed.products[row_index]
    if product.kind != 'AUXILIARY_CANDIDATE' or product.issues or not product.access_url:
        raise ValueError('Select an accessible auxiliary product row')
    url = urlsplit(product.access_url)
    if (url.scheme != 'https' or url.netloc not in [urlsplit(o).netloc for o in ARCHIVE_ORIGINS]
            or not url.path.startswith('/dataPortal/') or url.query or url.fragment
            or not url.path.endswith('.tar')):
        raise ValueError('Only official dataPortal auxiliary tar URLs are supported')
    return product, sha256(receipt_bytes).hexdigest(), parsed.requested_asdm_uid


def _digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def acquire_auxiliary(product, cache: Path, *, offline=False, open_url=None, max_download_bytes=None):
    """Cache publication is atomic; an entry is usable only after hash validation."""
    download_limit = MAX_DOWNLOAD if max_download_bytes is None else max_download_bytes
    if type(download_limit) is not int or not 0 < download_limit <= 1_000_000_000:
        raise ValueError('Download limit must be an integer between 1 and 1000000000 bytes')
    if product.content_length is not None and product.content_length > download_limit:
        raise ValueError('Advertised product exceeds download limit')
    cache.mkdir(parents=True, exist_ok=True)
    key = sha256(product.access_url.encode()).hexdigest()
    archive = cache / (key + '.tar')
    manifest = cache / (key + '.json')
    if archive.exists() or manifest.exists():
        if not archive.is_file() or not manifest.is_file():
            raise ValueError('Incomplete cache entry')
        record = json.loads(manifest.read_text())
        size = archive.stat().st_size
        if (record['url'] != product.access_url or size != record['bytes'] or size > download_limit
                or _digest(archive) != record['sha256']
                or product.content_length is not None and size != product.content_length):
            raise ValueError('Cache integrity mismatch')
        return archive, record, True
    if offline:
        raise ValueError('No verified cached product is available')
    started = datetime.now(timezone.utc).isoformat()
    deadline = time.monotonic() + 180
    opener = open_url or (lambda request: build_opener(_NoRedirect).open(request, timeout=30))
    temporary = None
    try:
        with opener(Request(product.access_url, headers={'Accept-Encoding': 'identity'})) as response:
            if response.status != 200:
                raise ValueError(f'Unexpected HTTP status: {response.status}')
            announced = response.headers.get('Content-Length')
            if announced is not None and (not announced.isdigit() or int(announced) > download_limit):
                raise ValueError('Invalid or oversized HTTP Content-Length')
            with tempfile.NamedTemporaryFile(dir=cache, suffix='.part', delete=False) as stream:
                temporary = Path(stream.name)
                size = 0
                for block in iter(lambda: response.read(65536), b''):
                    size += len(block)
                    if size > download_limit or time.monotonic() > deadline:
                        raise ValueError('Download budget exceeded')
                    stream.write(block)
        if ((announced is not None and size != int(announced))
                or product.content_length is not None and size != product.content_length):
            raise ValueError('Downloaded size does not match source metadata')
        record = dict(url=product.access_url, bytes=size, sha256=_digest(temporary),
                      started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                      http_status=200)
        # Hard-link publication refuses concurrent overwrite of an existing entry.
        os.link(temporary, archive)
        with manifest.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2)
            stream.write('\n')
        return archive, record, False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def inspect_auxiliary(archive: Path, *, asdm_uid: str, source_name: str, capture_dir: Path | None = None,
                      max_weblog_bytes=None, max_expanded_bytes=None):
    """Read regular listobs members only; no archive path is extracted to disk.

    Nested tar/tgz files are inspected within fixed shared budgets. Any skipped
    unsafe candidate or over-budget layout aborts selection rather than hiding ambiguity.
    Only nested archives named as weblogs are traversed; other packages are recorded.
    """
    weblog_limit = MAX_WEBLOG if max_weblog_bytes is None else max_weblog_bytes
    expanded_limit = MAX_EXPANDED if max_expanded_bytes is None else max_expanded_bytes
    for value, ceiling in ((weblog_limit, 1_000_000_000), (expanded_limit, 10_000_000_000)):
        if type(value) is not int or not 0 < value <= ceiling:
            raise ValueError('Invalid explicit inspection budget')
    if not re.fullmatch(r'uid://A[0-9A-Za-z]+/[0-9A-Za-z]+/[0-9A-Za-z]+', asdm_uid):
        raise ValueError('Invalid ASDM UID')
    if not source_name or source_name != source_name.strip():
        raise ValueError('Invalid target name')
    if capture_dir is not None:
        capture_dir.mkdir(exist_ok=False)
    budget = {'entries': 0, 'expanded': 0}
    skipped = []
    candidates, matches = [], []
    expected = asdm_uid.replace(':', '_').replace('/', '_') + '.ms'

    def visit(stream, chain, depth):
        with tarfile.open(fileobj=stream, mode='r|*') as tar:
            seen = set()
            for member in tar:
                budget['entries'] += 1
                budget['expanded'] += member.size
                if budget['entries'] > MAX_ENTRIES or budget['expanded'] > expanded_limit:
                    raise ValueError('Archive inspection budget exceeded')
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or '\\' in member.name or member.name in seen:
                    raise ValueError('Unsafe or repeated archive path')
                seen.add(member.name)
                if member.isdir():
                    continue
                lower = member.name.lower()
                nested = lower.endswith(('.tgz', '.tar.gz', '.tar'))
                listobs = 'listobs' in path.name.lower()
                if not member.isfile():
                    if listobs or nested:
                        raise ValueError('Linked candidate archive member is unsupported')
                    skipped.append(dict(path_chain=chain + [member.name], reason='NON_REGULAR_MEMBER'))
                    continue
                member_limit = weblog_limit if nested and 'weblog' in path.name.lower() else MAX_MEMBER
                if member.size < 0 or member.size > member_limit:
                    raise ValueError('Unsupported archive member size')
                if nested and 'weblog' not in path.name.lower():
                    skipped.append(dict(path_chain=chain + [member.name], reason='OUTSIDE_WEBLOG_SCOPE'))
                    continue
                if not nested and not listobs:
                    continue
                if nested and depth >= MAX_DEPTH:
                    raise ValueError('Archive nesting limit exceeded')
                if listobs and member.size > MAX_TEXT:
                    raise ValueError('Listobs size limit exceeded')
                location = chain + [member.name]
                if nested:
                    with tar.extractfile(member) as item:
                        visit(item, location, depth + 1)
                else:
                    with tar.extractfile(member) as item:
                        raw = item.read(member.size + 1)
                    if len(raw) != member.size:
                        raise ValueError('Truncated archive member')
                    if len(candidates) >= MAX_CANDIDATES:
                        raise ValueError('Listobs candidate limit exceeded')
                    entry = dict(path_chain=location, bytes=len(raw), sha256=sha256(raw).hexdigest())
                    candidates.append(entry)
                    if capture_dir is not None:
                        (capture_dir / (entry['sha256'] + '.txt')).write_bytes(raw)
                    text = raw.decode('utf-8')
                    headers = re.findall(r'^\s*MeasurementSet Name:\s+(.+?)\s+MS Version\s+\S+\s*$', text, re.M)
                    if len(headers) != 1:
                        entry['status'] = 'INVALID_HEADER'
                        continue
                    basename = PurePosixPath(headers[0].strip()).name
                    entry['measurement_set'] = basename
                    uid_match = re.fullmatch(r'uid___(A[0-9A-Za-z]+)_([0-9A-Za-z]+)_([0-9A-Za-z]+)(?:_target|_targets|_targets_line)?\.ms', basename)
                    if uid_match:
                        entry['reported_asdm_uid'] = 'uid://' + '/'.join(uid_match.groups())
                        entry['measurement_set_variant'] = 'TARGET' if basename.endswith(('_target.ms', '_targets.ms', '_targets_line.ms')) else 'ORIGINAL'
                    if basename != expected:
                        entry['status'] = 'OTHER_MEASUREMENT_SET'
                        continue
                    try:
                        evidence = parse_science_fields(raw, asdm_uid=asdm_uid, target_name=source_name)
                    except ValueError:
                        entry['status'] = 'MATCHING_MS_PARSE_FAILED'
                        continue
                    entry['status'] = 'MATCHED'
                    entry['science_field_count'] = len(evidence.fields)
                    matches.append((entry, raw))
    with archive.open('rb') as stream:
        visit(stream, [], 0)
    uncertain = any(c['status'] in ('INVALID_HEADER', 'MATCHING_MS_PARSE_FAILED') for c in candidates)
    status = ('UNRESOLVED_CANDIDATES' if uncertain else 'AMBIGUOUS' if len(matches) > 1
              else 'FOUND' if len(matches) == 1 else 'NOT_FOUND')
    return dict(status=status, candidates=candidates, budget=budget, skipped=skipped,
                scope='DIRECT_LISTOBS_AND_NESTED_WEBLOG_ARCHIVES_ONLY',
                selected=matches[0][0] if status == 'FOUND' else None), (matches[0][1] if status == 'FOUND' else None)


def acquire_listobs(receipt, row_index, cache, output, *, asdm_uid, source_name, offline=False):
    """Save an independent acquisition receipt and selected original listobs bytes."""
    product, receipt_hash, requested = select_auxiliary(receipt, row_index)
    if requested is not None and requested != asdm_uid:
        raise ValueError('Requested ASDM differs from discovery scope')
    output.mkdir(exist_ok=False)
    (output / 'discovery.json').write_bytes(receipt.read_bytes())
    (output / 'response.xml').write_bytes((receipt.parent / 'response.xml').read_bytes())
    record = dict(schema_version='archive_listobs_acquisition_1',
                  discovery_receipt_sha256=receipt_hash, product=asdict(product),
                  asdm_uid=asdm_uid, source_name=source_name,
                  completeness='MEMBER_COMPLETENESS_NOT_ESTABLISHED')
    try:
        archive, acquisition, hit = acquire_auxiliary(product, cache, offline=offline)
        record.update(acquisition=acquisition, cache_hit=hit)
        inspection, raw = inspect_auxiliary(archive, asdm_uid=asdm_uid, source_name=source_name)
        record.update(inspection=inspection, status=inspection['status'])
        if raw is not None:
            (output / 'listobs.txt').write_bytes(raw)
    except (OSError, ValueError, tarfile.TarError, EOFError, HTTPException) as exc:
        record.update(status='FAILED', error_type=type(exc).__name__, error=str(exc))
    (output / 'acquisition.json').write_text(json.dumps(record, indent=2) + '\n')
    return record
