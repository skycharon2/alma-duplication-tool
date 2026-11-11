"""Replay the fresh Rectangle export without changing the recorded audit."""

import csv
from hashlib import sha256
import json
from pathlib import Path

from astropy.coordinates import SkyCoord

from alma_duplicate.queue_mosaic_binding import _match
from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid

ROOT = Path(__file__).resolve().parents[2]


def main():
    folder = ROOT / "tests/fixtures/ot_pointings/rectangle_recheck_2026_11_10"
    audit = json.loads((folder / "audit.json").read_text())
    native = folder / "ot-7m-absolute.txt"
    assert sha256(native.read_bytes()).hexdigest() == audit["source_sha256"]
    lines = native.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("--")) + 1
    rows = list(csv.reader(lines[start:]))
    assert all(row[2:] == ["Absolute", "DEGREES"] for row in rows)
    reference = SkyCoord([[float(r[0]), float(r[1])] for r in rows], unit="deg")
    geometry = RectangleGeometry(150, -30, 0, 0, 100, 70, 0,
                                 27.804826215407775, "ICRS")
    grid = generate_rectangle_grid(geometry, 7, spacing_reference_diameter_m=12)
    predicted = SkyCoord([[p["ra_deg"], p["dec_deg"]] for p in grid["pointings"]],
                         unit="deg")
    distances = predicted[:, None].separation(reference[None, :]).arcsec
    matching = _match([[j for j, d in enumerate(row) if d <= 0.001]
                       for row in distances])
    assert len(matching) == len(predicted) == len(reference) == 5
    maximum = max(float(distances[i, j]) for i, j in matching.items())
    print(f"Fresh Rectangle 7-m: 5/5 matched; maximum residual {maximum:.9g} arcsec")


if __name__ == "__main__":
    main()
