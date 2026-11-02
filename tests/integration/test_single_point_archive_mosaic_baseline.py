"""Step 01 fixed cases, promoted to Step 03 position acceptance."""
import json
from pathlib import Path

import pytest

from alma_duplicate.mosaic_region_position import assess_region_position
from alma_duplicate.rules.position_single import evaluate_position_single
from tests.integration.test_confirmed_continuum import case, payload

FIXTURE = Path(__file__).parents[1] / "fixtures/single_point_archive_mosaic/position_cases.json"
CASES = json.loads(FIXTURE.read_text())["cases"]


@pytest.mark.parametrize("sample", CASES, ids=lambda sample: sample["id"])
def test_existing_region_geometry_for_future_single_point_contract(sample):
    """Exercise geometry only; deliberately do not reuse Mosaic majority outcome."""
    ra, dec = sample["point_deg"]
    proposal = {
        "points": [{"id": "target", "ra_deg": ra, "dec_deg": dec}],
        "frame_basis": "USER_CONFIRMED_FIXED_ICRS",
        "completeness": "USER_CONFIRMED_COMPLETE",
    }
    result = assess_region_position(proposal, sample["s_region"], candidate_id=sample["id"])
    assert result["points"][0]["status"] == sample["geometry_status"]


@pytest.mark.parametrize("sample", CASES, ids=lambda sample: sample["id"])
def test_single_point_mosaic_position_contract(sample):
    """Apply the approved single-point contract to each fixed geometry case."""
    request = payload()
    ra, dec = sample["point_deg"]
    request["request"]["position"].update(ra=ra, dec=dec)
    center_ra, center_dec = sample["candidate_center_deg"]
    proposed, context, evidence = case(
        request, mosaic="T", region=sample["s_region"],
        s_ra=center_ra, s_dec=center_dec,
    )
    result = evaluate_position_single(proposed, context, evidence)
    expected = sample["future_position_outcome"]
    assert (result.outcome.value if result.outcome else "UNKNOWN") == expected
    assert result.method_version == "archive_pos_single_mosaic_s_region_1"
