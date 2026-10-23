"""Parse native OT absolute pointing exports without changing row identity."""
import csv
import hashlib
import math
import re

MAX_BYTES = 2_000_000
MAX_ROWS = 10000


def _sexagesimal(value, *, ra):
    pattern = r'(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)' if ra else r'([+-]?\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)'
    match = re.fullmatch(pattern, value)
    if not match:
        raise ValueError('Invalid sexagesimal coordinate')
    first, minute, second = match.groups()
    a, b, c = abs(int(first)), int(minute), float(second)
    if b >= 60 or c >= 60 or a > (23 if ra else 90):
        raise ValueError('Sexagesimal component out of range')
    result = (a + b / 60 + c / 3600) * (-1 if first.startswith('-') else 1)
    return result * 15 if ra else result


def parse_ot_pointings(raw):
    """Accept one homogeneous Absolute export; preserve duplicates and original text."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('OT export must be bytes, at most 2 MB')
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    if len(lines) < 3:
        raise ValueError('Missing OT header or pointing rows')
    header = [s.strip().casefold() for s in next(csv.reader([lines[0]], strict=True))]
    if header != ['ra', 'dec', 'coordinate type', 'coordinate units']:
        raise ValueError('Expected OT pointings header, not a sources export')
    if not lines[1].strip().startswith('--'):
        raise ValueError('Missing OT header terminator')
    points, duplicates, seen = [], [], {}
    selected_unit = None
    for lineno, line in enumerate(lines[2:], 3):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line], strict=True))
            if len(row) != 4:
                raise ValueError('Expected four columns')
            ra_text, dec_text, kind, unit = [v.strip() for v in row]
            if kind.casefold() != 'absolute':
                raise ValueError('Export Absolute coordinates from OT; offsets are not supported yet')
            unit = unit.casefold()
            if unit not in ('degrees', 'radians', 'sexagesimal'):
                raise ValueError('Unsupported coordinate units')
            if selected_unit is not None and unit != selected_unit:
                raise ValueError('Mixed coordinate units in one export')
            selected_unit = unit
            if unit == 'sexagesimal':
                ra, dec = _sexagesimal(ra_text, ra=True), _sexagesimal(dec_text, ra=False)
            else:
                ra, dec = float(ra_text), float(dec_text)
                if unit == 'radians':
                    ra, dec = math.degrees(ra), math.degrees(dec)
            if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra < 360 or not -90 <= dec <= 90:
                raise ValueError('Coordinate outside valid range')
            if len(points) >= MAX_ROWS:
                raise ValueError('Pointing row limit exceeded')
        except (ValueError, csv.Error) as exc:
            raise ValueError(f'Line {lineno}: {exc}') from exc
        pid = f'row-{len(points) + 1}'
        key = (ra, dec)
        if key in seen:
            duplicates.append(dict(id=pid, same_coordinates_as=seen[key]))
        else:
            seen[key] = pid
        points.append(dict(id=pid, line_number=lineno, frame='ICRS', ra_deg=ra, dec_deg=dec,
                           ra_original=ra_text, dec_original=dec_text, raw_line=line))
    if not points:
        raise ValueError('No pointing rows')
    return dict(schema_version='ot_pointings_1', input_sha256=hashlib.sha256(raw).hexdigest(),
                raw_text=text, coordinate_units=selected_unit, row_count=len(points), points=points,
                duplicate_coordinates=duplicates, identity_rule='ONE_INPUT_ROW_ONE_POINTING',
                frame_basis='CALLER_MUST_CONFIRM_FIXED_ICRS', completeness='NOT_CONFIRMED')
