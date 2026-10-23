"""Read the supported verbose CASA SPW and antenna tables without inferred defaults."""
import math
import re


def parse_spectral_windows(raw: bytes):
    text = raw.decode('utf-8')
    declarations = list(re.finditer(r'^Spectral Windows:\s*\((\d+) unique spectral windows.*\)\s*$', text, re.M))
    if len(declarations) != 1:
        raise ValueError('Expected one declared spectral-window table')
    section = text[declarations[0].end():].split('Sources:', 1)[0]
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    if not lines or lines[0].split() != ['SpwID', 'Name', '#Chans', 'Frame', 'Ch0(MHz)', 'ChanWid(kHz)', 'TotBW(kHz)', 'CtrFreq(MHz)', 'BBC', 'Num', 'Corrs']:
        raise ValueError('Unsupported spectral-window columns or units')
    windows = {}
    for line in lines[1:]:
        cells = line.split()
        if len(cells) < 10:
            raise ValueError('Malformed spectral-window row')
        try:
            sid, count, bbc = int(cells[0]), int(cells[2]), int(cells[8])
            first, width, bandwidth, centre = map(float, cells[4:8])
        except ValueError as exc:
            raise ValueError('Invalid spectral-window numeric value') from exc
        if (sid < 0 or sid in windows or count < 1 or not all(math.isfinite(v) for v in (first, width, bandwidth, centre))
                or first <= 0 or centre <= 0 or width == 0 or bandwidth <= 0):
            raise ValueError('Invalid or duplicate spectral-window values')
        first_hz, width_hz = first * 1e6, width * 1e3
        last_hz = first_hz + (count - 1) * width_hz
        low = min(first_hz, last_hz) - abs(width_hz) / 2
        high = max(first_hz, last_hz) + abs(width_hz) / 2
        if low <= 0 or not all(math.isfinite(v) for v in (low, high)):
            raise ValueError('Invalid derived spectral interval')
        windows[sid] = dict(spw_id=sid, name=cells[1], channel_count=count, frame=cells[3],
            first_channel_hz=first_hz, signed_channel_width_hz=width_hz,
            reported_total_bandwidth_hz=bandwidth * 1e3, reported_centre_hz=centre * 1e6,
            approximate_frequency_range_hz=[low, high],
            frequency_range_method='UNIFORM_CHANNEL_GRID_FROM_ROUNDED_LISTOBS_VALUES',
            exact_channel_edges_status='NOT_AVAILABLE', bbc_number=bbc, correlations=cells[9:],
            raw_row=line, raw_units=dict(first_channel='MHz', channel_width='kHz', bandwidth='kHz', centre='MHz'))
    if len(windows) != int(declarations[0].group(1)):
        raise ValueError('Incomplete spectral-window table')
    return windows


def parse_antennas(raw: bytes):
    text = raw.decode('utf-8')
    declarations = list(re.finditer(r'^Antennas:\s*(\d+):\s*$', text, re.M))
    if len(declarations) != 1:
        raise ValueError('Expected one verbose antenna table')
    section = text[declarations[0].end():]
    if not re.search(r'ID\s+Name\s+Station\s+Diam\.', section):
        raise ValueError('Missing antenna diameter columns')
    antennas = {}
    for line in section.splitlines():
        if not re.match(r'^\s*\d+\s', line):
            continue
        cells = line.split()
        if len(cells) < 6 or cells[4] != 'm':
            raise ValueError('Unsupported antenna row or diameter unit')
        aid, diameter = int(cells[0]), float(cells[3])
        if aid in antennas or not math.isfinite(diameter) or diameter <= 0:
            raise ValueError('Invalid or duplicate antenna diameter')
        antennas[aid] = dict(antenna_id=aid, name=cells[1], station=cells[2], diameter_m=diameter, raw_row=line.strip())
    if len(antennas) != int(declarations[0].group(1)) or not antennas:
        raise ValueError('Incomplete antenna table')
    diameters = sorted({a['diameter_m'] for a in antennas.values()})
    return dict(antennas=list(antennas.values()), diameters_m=diameters,
                dish_class='7M' if diameters == [7.0] else '12M' if diameters == [12.0] else 'MIXED' if len(diameters) > 1 else 'OTHER',
                scope='EXECUTION_LISTOBS_ANTENNA_TABLE_NOT_PER_FIELD_ACTIVE_BASELINES')
