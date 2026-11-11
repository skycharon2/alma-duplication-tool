"""Replay two bounded OT experiments; no production geometry is changed."""
from hashlib import sha256
import json
from pathlib import Path

from plot_c1 import read_native
from probe_c1 import candidates, score

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/ot_pointings/custom_minimal_2026_11_11'


def main():
    frequency_reference = read_native(FIXTURE / 'line-first105-lowest93-7m.txt')
    result = {'status': 'LIMITED_EXPERIMENTAL_SUPPORT', 'frequency_cases': [], 'files': {}}
    for name in ['line-first105-lowest93-7m.txt', 'asymmetric-7m.txt',
                 'asymmetric-predictions.json']:
        result['files'][name] = sha256((FIXTURE / name).read_bytes()).hexdigest()
    for label, frequency in [('first_rest', 105), ('first_displayed_sky', 104.99816),
                             ('target_representative_sky', 104.99555),
                             ('lowest_rest', 93), ('lowest_displayed_sky', 92.99837)]:
        hypotheses = candidates(frequency)
        comparisons = [score(h['predicted_pointings'], frequency_reference) for h in hypotheses]
        best = min((c for c in comparisons if 'max_residual_arcsec' in c),
                   key=lambda c: c['max_residual_arcsec'])
        result['frequency_cases'].append(dict(label=label, frequency_ghz=frequency, best=best))
    predictions = json.loads((FIXTURE / 'asymmetric-predictions.json').read_text())
    reference = read_native(FIXTURE / 'asymmetric-7m.txt')
    for hypothesis in predictions['hypotheses']:
        hypothesis['comparison'] = score(hypothesis['predicted_pointings'], reference)
    result['asymmetric'] = predictions
    matches = [h for h in predictions['hypotheses'] if h['comparison']['status'] == 'MATCHED']
    assert len(matches) == 1
    assert matches[0]['rectangle_hypothesis'] == 'MINIMUM_AREA_CENTRES'
    assert all(c['best']['status'] == 'MISMATCH' for c in result['frequency_cases'][:3])
    assert result['frequency_cases'][-1]['best']['status'] == 'MATCHED'
    output = ROOT / 'reports/custom-aca-minimal'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    for case in result['frequency_cases']:
        print(case['label'], case['best']['max_residual_arcsec'])
    print('Asymmetric maximum residual:', matches[0]['comparison']['max_residual_arcsec'])


if __name__ == '__main__':
    main()
