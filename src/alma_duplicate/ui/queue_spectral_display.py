"""Read-only spectral coverage saved with one Queue array branch."""
import json
import math
from fractions import Fraction


def continuum_windows(records):
    coverage = []
    for record in records:
        if record.get('criterion_id') != 'CONT-RMS':
            continue
        try:
            windows = json.loads(dict(record.get('details') or []).get('spw_evidence_json', '[]'))
        except (ValueError, TypeError):
            continue
        if not isinstance(windows, list):
            continue
        for window in windows:
            try:
                low, high = [float(Fraction(v)) for v in window['usable_interval_ghz_exact']]
            except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
                continue
            if math.isfinite(low) and math.isfinite(high) and 0 < low < high:
                coverage.append(dict(low=low, high=high, bandwidth_ghz=high-low, spw=window.get('spw_number')))
    return coverage
