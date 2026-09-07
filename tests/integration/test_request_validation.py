import json
from pathlib import Path

from alma_duplicate.request_validation import validate_proposed_observation

EXAMPLE = Path(__file__).parents[2] / "examples" / "proposed_observation.json"


def test_full_offline_input_to_request_and_report():
    payload = json.loads(EXAMPLE.read_text())
    report = validate_proposed_observation(
        payload["request"], payload["search_options"]
    )
    assert report.is_valid and report.can_search
    assert report.request.position.ra_deg == 180
    assert report.request.position.dec_deg == -0.5
    assert report.request.spectral_windows[0].bandwidth is None
    assert report.request.spectral_windows[0].interval is None
    assert report.request.sensitivities[0].rms.value == 1
    assert report.request.sensitivities[0].window_ids == ()
    assert report.request.sensitivities[1].window_ids == ("w1",)
    assert {issue.side for issue in report.issues} <= {"PROPOSED", "METHOD"}
    assert not hasattr(report, "duplicate")
    assert not hasattr(report, "candidates")
    # Frozen raw wire representation can be validated again without losing roles.
    second = validate_proposed_observation(report.raw_input, report.raw_search_options)
    assert second.request == report.request
    assert second.issues == report.issues


def test_invalid_field_preserves_raw_input_but_suppresses_executable_outputs():
    payload = json.loads(EXAMPLE.read_text())
    payload["request"]["spectral_windows"][0]["bandwidth"] = {
        "value": -2,
        "unit": "GHz",
    }
    report = validate_proposed_observation(
        payload["request"], payload["search_options"]
    )
    assert report.request is report.search_options is None
    assert report.search_readiness == "BLOCKED"
    assert report.raw_input["spectral_windows"][0]["bandwidth"]["value"] == -2
    assert any(
        issue.path == "request.spectral_windows[0].bandwidth" for issue in report.errors
    )
