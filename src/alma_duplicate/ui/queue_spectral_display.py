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
                item = dict(low=low, high=high, bandwidth_ghz=high-low, spw=window.get('spw_number'))
                # Nominal boundaries come only from saved SKY centre and width.
                try:
                    centre = float(Fraction(str(window['sky_frequency_ghz'])))
                    width = float(Fraction(str(window['nominal_bandwidth_mhz']))) / 1000
                    if all(math.isfinite(v) for v in (centre, width)) and width > 0 and centre-width/2 > 0:
                        item.update(nominal_low=centre-width/2, nominal_high=centre+width/2)
                except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError):
                    pass
                coverage.append(item)
    return coverage
