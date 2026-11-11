"""Replay archived frequency observations; do not infer a production rule."""

from hashlib import sha256
import json

import numpy as np

from plot_c1 import OUT, ROOT, read_native
from probe_c1 import candidates, score


def main():
    folder = ROOT / "tests/fixtures/ot_pointings/custom_frequency_2026_11_10"
    audit = json.loads((folder / "audit.json").read_text())
    coordinates = {}
    for name, recorded in audit["files"].items():
        path = folder / name
        assert sha256(path.read_bytes()).hexdigest() == recorded["sha256"], name
        coords = coordinates[name] = read_native(path)
        assert len(coords) == recorded["count"], name
        separations = [float(coords[i].separation(coords[j]).arcsec)
                       for i in range(len(coords)) for j in range(i + 1, len(coords))]
        np.testing.assert_allclose(separations, recorded["pair_separations_arcsec"],
                                   rtol=0, atol=1e-6)
    assert (folder / "baseline-7m.txt").read_bytes() == (
        folder / "representative-106p5-7m.txt").read_bytes()
    replay = {"status": "EXPLORATORY_NOT_VALIDATED", "cases": []}
    for frequency, filename in [(93, "baseline-7m.txt"), (94, "continuum-101-7m.txt")]:
        hypotheses = candidates(frequency)
        reference = coordinates[filename]
        for candidate in hypotheses:
            candidate["comparison"] = score(candidate["predicted_pointings"], reference)
        recorded = audit[f"hypotheses_at_{frequency}_ghz"]
        assert len(hypotheses) == len(recorded)
        for candidate, old in zip(hypotheses, recorded):
            assert candidate["rectangle_hypothesis"] == old["hypothesis"]
            for key, value in candidate["input_geometry"].items():
                if isinstance(value, (int, float)):
                    np.testing.assert_allclose(value, old["geometry"][key], rtol=0, atol=1e-8)
                else:
                    assert value == old["geometry"][key]
            assert candidate["comparison"]["status"] == old["comparison"]["status"]
            if "max_residual_arcsec" in old["comparison"]:
                np.testing.assert_allclose(candidate["comparison"]["max_residual_arcsec"],
                                           old["comparison"]["max_residual_arcsec"],
                                           rtol=0, atol=1e-6)
        matches = [h for h in hypotheses if h["comparison"]["status"] == "MATCHED"]
        assert matches
        # Confirm scoring is independent of row order and rejects incomplete/displaced sets.
        points = matches[0]["predicted_pointings"]
        assert score(points, reference[::-1])["status"] == "MATCHED"
        assert score(points[:-1], reference)["status"] == "COUNT_MISMATCH"
        displaced = [dict(p, ra_deg=p["ra_deg"] + 0.01) for p in points]
        assert score(displaced, reference)["status"] == "MISMATCH"
        replay["cases"].append(dict(frequency_ghz=frequency, hypotheses=hypotheses))
        print(f"{frequency} GHz: {len(matches)}/{len(hypotheses)} hypotheses match archived output")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frequency-replay.json").write_text(json.dumps(replay, indent=2) + "\n")
    print("File hashes, counts, separations and archived hypothesis scores verified.")


if __name__ == "__main__":
    main()
