"""Offline, row-preserving import of independent fixed ICRS targets.

File-level failures raise ValueError. Row errors remain in the preview and make
is_valid false; callers must not silently execute only the valid subset.
"""
import csv
import hashlib
import math
import re
import shlex
from decimal import Decimal, InvalidOperation

from alma_duplicate.request_validation import validate_preview_position

MAX_BYTES = 100_000
MAX_SOURCES = 5
_NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')


def parse_source_list(raw: bytes, *, format: str = 'csv', max_sources: int = MAX_SOURCES):
    """Read headered CSV or whitespace TXT (quoted names allowed).

    Headers: name, ra, dec, optional redshift (case insensitive, any order).
    Decimal coordinates mean degrees; colon RA means hours, colon Dec degrees.
    IDs are local to this input: combine with batch_id when storing reports.
    Redshift is preserved as decimal text, including explicit zero; absent is None.
    """
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError(f'Source list must be bytes, at most {MAX_BYTES} bytes')
    if format not in {'csv', 'txt'}:
        raise ValueError('Source list format must be csv or txt')
    if type(max_sources) is not int or max_sources < 1:
        raise ValueError('max_sources must be a positive integer')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Source list must be UTF-8 text') from exc
    if '\x00' in text:
        raise ValueError('Source list contains a NUL character')

    def fields(line):
        if format == 'csv':
            return [value.strip() for value in next(csv.reader([line], strict=True))]
        return shlex.split(line, comments=False)

    lines = [(number, line) for number, line in enumerate(text.splitlines(), 1)
             if line.strip() and not line.lstrip().startswith('#')]
    if not lines:
        raise ValueError('Missing source-list header')
    try:
        header = [value.casefold() for value in fields(lines[0][1])]
    except (csv.Error, ValueError) as exc:
        raise ValueError('Malformed source-list header') from exc
    if (len(header) != len(set(header)) or
            set(header) not in ({'name', 'ra', 'dec'}, {'name', 'ra', 'dec', 'redshift'})):
        raise ValueError('Expected name, ra, dec and optional redshift columns')
    if len(lines) == 1:
        raise ValueError('No source rows')
    if len(lines) - 1 > max_sources:
        raise ValueError(f'Source limit exceeded: at most {max_sources} rows')

    sources, seen_names, seen_positions = [], {}, {}
    for number, line in lines[1:]:
        source = dict(source_id=f'line-{number}', line_number=number, raw_line=line,
                      name=None, ra_deg=None, dec_deg=None, redshift=None,
                      frame='ICRS', original={}, issues=[])
        sources.append(source)

        def issue(code, field, message, severity='ERROR'):
            source['issues'].append(dict(code=code, field=field, message=message,
                                         severity=severity, line_number=number))

        try:
            values = fields(line)
        except (csv.Error, ValueError):
            issue('INVALID_ROW', 'row', 'Malformed quoting; use one source per physical line.')
            continue
        if len(values) != len(header):
            issue('COLUMN_COUNT', 'row', f'Expected {len(header)} columns, got {len(values)}.')
            continue
        original = dict(zip(header, values))
        source['original'] = original
        source['name'] = original['name']
        if not source['name']:
            issue('MISSING_NAME', 'name', 'Supply a target name.')
        position, diagnostics = validate_preview_position(dict(
            ra=original['ra'], dec=original['dec'], frame='ICRS',
            ra_format='HMS' if ':' in original['ra'] else 'DEG',
            dec_format='DMS' if ':' in original['dec'] else 'DEG'))
        for diagnostic in diagnostics:
            issue(diagnostic.code, diagnostic.path.rsplit('.', 1)[-1], diagnostic.message)
        if position is not None and not diagnostics:
            source['ra_deg'], source['dec_deg'] = position.ra_deg, position.dec_deg
        redshift = original.get('redshift', '')
        if redshift:
            try:
                value = Decimal(redshift)
                if (not _NUMBER.fullmatch(redshift) or not value.is_finite() or
                        value <= -1 or not math.isfinite(float(value)) or float(value) <= -1):
                    raise ValueError
            except (InvalidOperation, ValueError, OverflowError):
                issue('INVALID_REDSHIFT', 'redshift', 'Require a finite numeric redshift z > -1.')
            else:
                source['redshift'] = redshift
        if source['name']:
            if source['name'] in seen_names:
                issue('DUPLICATE_NAME', 'name',
                      f"Same name as {seen_names[source['name']]}; both rows retained.", 'WARNING')
            else:
                seen_names[source['name']] = source['source_id']
        if source['ra_deg'] is not None:
            key = (source['ra_deg'], source['dec_deg'])
            if key in seen_positions:
                issue('DUPLICATE_POSITION', 'position',
                      f'Same coordinates as {seen_positions[key]}; both rows retained.', 'WARNING')
            else:
                seen_positions[key] = source['source_id']
    for source in sources:
        source['is_valid'] = not any(i['severity'] == 'ERROR' for i in source['issues'])
    return dict(schema_version='source_list_1', input_sha256=hashlib.sha256(raw).hexdigest(),
                raw_text=text, format=format, row_count=len(sources), sources=sources,
                is_valid=all(source['is_valid'] for source in sources),
                identity_rule='ONE_INPUT_ROW_ONE_SOURCE', frame_basis='INPUT_CONTRACT_ICRS')
