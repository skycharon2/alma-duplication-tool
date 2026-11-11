"""Diagnostic hypotheses from C1 inputs; OT output is loaded only for scoring."""
from dataclasses import asdict
from itertools import permutations
import json
import math

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid
from plot_c1 import FIXTURE, OUT, read_native

INPUT = np.array([(0, 0), (15, 0), (-15, 0), (0, 15), (0, -15),
                  (10, 10), (-10, -10)], dtype=float)
FREQUENCY_GHZ = 107
TOLERANCE_ARCSEC = 0.001


def candidates(frequency_ghz=FREQUENCY_GHZ):
    # All pair directions include convex-hull edges, hence minimum-area rectangle
    # orientations. No OT output coordinates enter this construction.
    angles = {0.0}
    for a in INPUT:
        for b in INPUT:
            delta = b - a
            if np.any(delta):
                angles.add(round(math.degrees(math.atan2(-delta[1], delta[0])) % 90, 10))
    boxes = []
    for angle in sorted(angles):
        rad = math.radians(angle)
        basis = np.array([[math.cos(rad), -math.sin(rad)],
                          [math.sin(rad), math.cos(rad)]])
        local = INPUT @ basis.T
        low, high = local.min(axis=0), local.max(axis=0)
        boxes.append((angle, float(np.prod(high - low))))
    minimum = min(area for _, area in boxes)
    chosen = [("AXIS_ALIGNED", 0.0)] + [
        ("MINIMUM_AREA_CENTRES", angle) for angle, area in boxes
        if math.isclose(area, minimum, abs_tol=1e-7)]
    wavelength = 299792458 / (frequency_ghz * 1e9)
    arcsec = 180 * 3600 / math.pi
    spacing7 = wavelength / (math.sqrt(3) * 7) * arcsec
    beam12 = 1.13 * wavelength / 12 * arcsec
    results = []
    for kind, base_angle in chosen:
        # Rectangle symmetry does not guarantee triangular-grid phase symmetry.
        # Retain all equivalent orientations rather than selecting by residual.
        for rotation in (0, 90, 180, 270):
            angle = base_angle + rotation
            rad = math.radians(angle)
            basis = np.array([[math.cos(rad), -math.sin(rad)],
                              [math.sin(rad), math.cos(rad)]])
            local = INPUT @ basis.T
            low, high = local.min(axis=0), local.max(axis=0)
            centre = ((low + high) / 2) @ basis
            for padding in (0.0, beam12):
                geometry = RectangleGeometry(150, -30, *centre,
                    *(high - low + padding), angle, spacing7, "ICRS")
                grid = generate_rectangle_grid(geometry, 7,
                                               spacing_reference_diameter_m=7)
                results.append(dict(rectangle_hypothesis=kind,
                    total_dimension_padding_arcsec=padding,
                    input_geometry=asdict(geometry),
                    predicted_pointings=grid["pointings"],
                    generation_reasons=grid["reasons"]))
    return results


def score(points, reference):
    if len(points) != len(reference):
        return dict(status="COUNT_MISMATCH", predicted_count=len(points),
                    reference_count=len(reference))
    if len(points) > 8:
        raise ValueError("Exhaustive assignment is limited to this small diagnostic")
    coords = SkyCoord([p["ra_deg"] for p in points] * u.deg,
                      [p["dec_deg"] for p in points] * u.deg)
    distances = coords[:, None].separation(reference[None, :]).arcsec
    assignment = min(permutations(range(len(reference))),
                     key=lambda p: max(distances[i, j] for i, j in enumerate(p)))
    residuals = [float(distances[i, j]) for i, j in enumerate(assignment)]
    return dict(status="MATCHED" if max(residuals) <= TOLERANCE_ARCSEC else "MISMATCH",
                reference_indices=list(assignment), residuals_arcsec=residuals,
                max_residual_arcsec=max(residuals), median_residual_arcsec=float(np.median(residuals)))


def main():
    hypotheses = candidates()
    # Predictions are fixed before the native 7-m reference is read.
    reference = read_native(FIXTURE / "ot-7m-absolute.txt")
    spacing = 299792458 / (FREQUENCY_GHZ * 1e9 * math.sqrt(3) * 7) * 180 * 3600 / math.pi
    pair_distances = [float(reference[i].separation(reference[j]).arcsec)
                      for i in range(len(reference)) for j in range(i + 1, len(reference))]
    for candidate in hypotheses:
        candidate["comparison"] = score(candidate["predicted_pointings"], reference)
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(status="EXPLORATORY_NOT_VALIDATED", scientific_status="NOT_EVALUATED",
        input_offsets_arcsec=INPUT.tolist(), frequency_ghz=FREQUENCY_GHZ,
        tolerance_arcsec=TOLERANCE_ARCSEC,
        spacing_diagnostic=dict(nominal_7m_nyquist_arcsec=spacing,
            native_pair_separations_arcsec=pair_distances,
            pair_to_nominal_ratios=[d / spacing for d in pair_distances],
            equivalent_nyquist_frequency_ghz=[FREQUENCY_GHZ * spacing / d
                                              for d in pair_distances],
            interpretation="Observed separations only; not an adopted spacing correction"),
        limitations=["Single known reference; hypothesis selection is not independent validation",
                     "Padding, rectangle orientation and pruning remain unverified",
                     "No redundancy removal implemented"], hypotheses=hypotheses)
    (OUT / "c1-hypothesis-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    for candidate in hypotheses:
        c = candidate["comparison"]
        print(candidate["rectangle_hypothesis"],
              'PA=', candidate["input_geometry"]["pa_deg"],
              'padding=', round(candidate["total_dimension_padding_arcsec"], 5),
              'count=', len(candidate["predicted_pointings"]), c["status"],
              c.get("max_residual_arcsec", ""))


if __name__ == "__main__":
    main()
