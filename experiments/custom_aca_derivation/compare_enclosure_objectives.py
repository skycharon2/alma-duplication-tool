"""A precomputed discriminator for centre-area versus padded-area objectives."""
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

import numpy as np

from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid
from plot_c1 import read_native
from probe_c1 import score

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/ot_pointings/custom_enclosure_2026_11_11'
POINTS = np.array([(0, 0), (-30, -10), (-15, 0), (0, 15), (0, -15),
                   (10, 10), (-10, -10)], dtype=float)
FREQUENCY_GHZ = 93
BEAM = 1.13 * 299792458 / (FREQUENCY_GHZ * 1e9 * 12) * 180 * 3600 / math.pi
SPACING = 299792458 / (FREQUENCY_GHZ * 1e9 * math.sqrt(3) * 7) * 180 * 3600 / math.pi


def hull(points):
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    ordered = sorted(set(map(tuple, points)))
    halves = []
    for sequence in (ordered, ordered[::-1]):
        half = []
        for point in sequence:
            while len(half) >= 2 and cross(half[-2], half[-1], point) <= 0:
                half.pop()
            half.append(point)
        halves.append(half[:-1])
    return np.array(halves[0] + halves[1])


def box(angle):
    rad = math.radians(angle)
    basis = np.array([[math.cos(rad), -math.sin(rad)],
                      [math.sin(rad), math.cos(rad)]])
    local = POINTS @ basis.T
    low, high = local.min(axis=0), local.max(axis=0)
    return high-low, ((low+high)/2) @ basis


def predict():
    vertices = hull(POINTS)
    edges = np.roll(vertices, -1, axis=0)-vertices
    angles = sorted({math.degrees(math.atan2(-d[1], d[0])) % 90 for d in edges})
    boxes = []
    for angle in angles:
        wh, centre = box(angle)
        boxes.append(dict(angle_deg=angle, dimensions_arcsec=wh.tolist(),
                          centre_offset_arcsec=centre.tolist(),
                          centre_area=float(np.prod(wh)), padded_area=float(np.prod(wh+BEAM))))
    models = []
    for objective in ('centre_area', 'padded_area'):
        best = min(boxes, key=lambda b: b[objective])
        # Independent dense angular check, including non-edge directions. This is
        # a numerical sanity check, not a theorem for arbitrary padded polygons.
        dense_min = min(float(np.prod(box(a)[0] + (BEAM if objective == 'padded_area' else 0)))
                        for a in np.linspace(0, 90, 18001))
        assert best[objective] <= dense_min + 1e-7
        for rotation in (0, 90, 180, 270):
            angle = best['angle_deg'] + rotation
            wh, centre = box(angle)
            geometry = RectangleGeometry(150, -30, *centre, *(wh+BEAM), angle, SPACING, 'ICRS')
            grid = generate_rectangle_grid(geometry, 7, spacing_reference_diameter_m=7)
            models.append(dict(objective=objective, geometry=asdict(geometry),
                               pointings=grid['pointings'], reasons=grid['reasons']))
    return dict(input_offsets_arcsec=POINTS.tolist(), frequency_ghz=FREQUENCY_GHZ,
                total_dimension_padding_arcsec=BEAM, hull_vertices=vertices.tolist(),
                candidate_boxes=boxes, models=models,
                limitations=['No pruning', 'Four directed orientations retained',
                             'Padding fixed to the existing FWHM hypothesis'])


def main():
    FIXTURE.mkdir(parents=True, exist_ok=True)
    path = FIXTURE / 'predictions.json'
    if '--score' not in sys.argv:
        # Never overwrite the predictions frozen before OT export.
        with path.open('x') as stream:
            stream.write(json.dumps(predict(), indent=2)+'\n')
        print(path)
        return
    predictions = json.loads(path.read_text())
    assert predictions == predict()
    native = FIXTURE / 'ot-7m-absolute.txt'
    reference = read_native(native)
    for model in predictions['models']:
        model['comparison'] = score(model['pointings'], reference)
        print(model['objective'], model['geometry']['pa_deg'], model['comparison'])
    matches = [m for m in predictions['models'] if m['comparison']['status'] == 'MATCHED']
    assert len(matches) == 1 and matches[0]['objective'] == 'centre_area'
    predictions['reference_sha256'] = sha256(native.read_bytes()).hexdigest()
    predictions['predictions_sha256'] = sha256(path.read_bytes()).hexdigest()
    output = ROOT / 'reports/custom-aca-enclosure'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'audit.json').write_text(json.dumps(predictions, indent=2)+'\n')


if __name__ == '__main__':
    main()
