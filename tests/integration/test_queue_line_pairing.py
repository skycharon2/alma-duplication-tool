"""Queue same-pair provenance and offline preparation acceptance."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from alma_duplicate.cli.queue_line_pairs import main
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from alma_duplicate.request_validation import validate_proposed_observation
from tests.integration.test_candidate_search import queue_rows
from tests.unit.test_queue_csv_parser import _parse_fixture


ROOT = Path(__file__).parents[2]


def request():
    p = json.loads((ROOT / "examples/confirmed_line/request.json").read_text())
    return validate_proposed_observation(p["request"], p["search_options"]).request


def contexts(*changes):
    base = {"Project Code": "2024.1.00001.S", "Polarization": "DOUBLE",
            "Use TP?": "False", "Use 7-m?": "False", "Is Sky Freq?": "True"}
    for n, resolution in enumerate((0.9765625, 31.25, 0.123, 0.9765625), 1):
        base.update({f"Freq SPW {n}": str(220 + 2 * n),
                     f"Bandwidth SPW {n}": "1875",
                     f"Spec.Res. SPW {n}": str(resolution)})
    source = build_queue_contexts(queue_rows(*(base | c for c in (changes or ({},)))))
    assert source.status == "COMPLETE", source.reasons
    return source.contexts


def test_all_windows_times_spws_keep_same_pair_evidence():
    req, context = request(), contexts()[0]
    req = replace(req, spectral_windows=(*req.spectral_windows,
                  replace(req.spectral_windows[0], window_id="no-rms")))
    result = build_queue_line_pairs(req, context)
    assert len(result.attempts) == 8  # Includes out-of-band and missing-RMS attempts.
    assert result.proposed_enumeration_complete and result.candidate_enumeration_complete
    assert result.assessment == "NOT_EVALUATED"
    assert [a.candidate.mode["mode_evidence"]["mode"] for a in result.attempts[:4]] == [
        "FDM", "TDM", "UNKNOWN", "FDM"]
    for a in result.attempts:
        proposed, candidate = a.reference.resolve(req, context)
        slot = context.evidence.row.spectral.spws[a.reference.spw_number - 1]
        assert candidate.spw is slot
        assert candidate.spw.frequency_derivation.sky_frequency_ghz == 220 + 2 * slot.number
        assert candidate.spw.usable_lower_sky_frequency_ghz == 220 + 2 * slot.number - .9375
        assert candidate.sensitivity_reference is context.evidence.row.spectral.sensitivity
        assert candidate.mode["source"]["resolution_raw_mhz"] == slot.spectral_resolution_mhz.raw_text
        assert candidate.mode["source"]["spw_number"] == slot.number
        assert candidate.mode["mode_evidence"]["method_version"] == "queue_mode_evidence_adapter_2"
        if proposed.window_id == "no-rms":
            assert proposed.sensitivity_id is None
            assert "UNIQUE_WINDOW_LINE_SENSITIVITY_REQUIRED" in a.reasons
    assert "QUEUE_MODE_UNRESOLVED" in result.attempts[2].reasons


@pytest.mark.parametrize("change", ["context", "row", "snapshot", "association", "fingerprint", "spw", "setup"])
def test_resolve_rejects_foreign_and_ambiguous_evidence(change):
    req = request()
    c, other = contexts({}, {})  # Same values, different physical rows.
    ref = build_queue_line_pairs(req, c).attempts[0].reference
    if change == "context":
        c = replace(c, context_id="other")
    elif change == "row":
        c = other
    elif change == "snapshot":
        c = replace(c, reference=replace(c.reference, source_record_id="0" * 64))
    elif change == "association":
        c = replace(c, evidence=replace(c.evidence, association=other.evidence.association))
    elif change == "fingerprint":
        ref = replace(ref, content_fingerprint="0" * 64)
    elif change == "spw":
        row = c.evidence.row
        row = replace(row, spectral=replace(row.spectral, spws=(row.spectral.spws[0],) * 2))
        c = replace(c, evidence=replace(c.evidence, row=row))
    else:
        req = replace(req, setup_id="other")
    with pytest.raises(ValueError):
        ref.resolve(req, c)


def test_no_cross_row_reference_sensitivity_and_no_cross_window_rms():
    req = request()
    c1, c2 = contexts({"Req.Sensitivity": "1"}, {"Req.Sensitivity": "9"})
    a1 = build_queue_line_pairs(req, c1).attempts[0]
    a2 = build_queue_line_pairs(req, c2).attempts[0]
    assert a1.candidate.sensitivity_reference.requested_sensitivity_mjy.value == 1
    assert a2.candidate.sensitivity_reference.requested_sensitivity_mjy.value == 9
    foreign = replace(req.sensitivities[0], setup_id="foreign")
    a = build_queue_line_pairs(replace(req, sensitivities=(foreign,)), c1).attempts[0]
    assert a.proposed.sensitivity_id is None
    with pytest.raises(ValueError):
        replace(a1, candidate=a2.candidate)


def test_no_partial_or_unknown_evidence_is_a_negative():
    req = replace(request(), setup_complete=False, sensitivities=())
    result = build_queue_line_pairs(req, contexts({"Bandwidth SPW 3": "800"})[0])
    assert not result.proposed_enumeration_complete
    assert len(result.attempts) == 4
    assert "QUEUE_USABLE_INTERVAL_REQUIRED" in result.attempts[2].reasons
    assert all(a.evidence_status == "INCOMPLETE" for a in result.attempts)
    assert result.assessment == "NOT_EVALUATED"


def test_scope_diagnostics_preserve_pairs_without_scientific_pass():
    result = build_queue_line_pairs(request(), contexts({"Mosaic": "Custom"})[0])
    assert result.reasons and len(result.attempts) == 4
    assert all(a.reasons for a in result.attempts)
    assert result.assessment == "NOT_EVALUATED"


def test_tp_flag_is_not_a_pair_preparation_blanket_blocker():
    result = build_queue_line_pairs(request(), contexts({"Use TP?": "True"})[0])
    assert "TP_RULES_OUTSIDE_CURRENT_SCOPE" not in result.reasons
    assert all("TP_RULES_OUTSIDE_CURRENT_SCOPE" not in a.reasons for a in result.attempts)
    assert len(result.attempts) == 4 and result.assessment == "NOT_EVALUATED"


def test_rest_to_sky_and_raw_hardware_width_are_retained():
    c = contexts({"Is Sky Freq?": "False", "Velocity": "30000",
                  "Vel. Convention": "OPTICAL"})[0]
    candidate = build_queue_line_pairs(request(), c).attempts[0].candidate
    assert candidate.spw.frequency_derivation.sky_frequency_ghz == pytest.approx(222 / (1 + 30000 / 299792.458))
    assert candidate.spw.frequency_ghz.raw_text == "222"
    assert candidate.spw.usable_bandwidth_ghz == 1.875


def test_spectral_scan_and_unselected_and_empty_are_explicit():
    source = build_queue_contexts(_parse_fixture())
    scan = next(c for c in source.contexts if not hasattr(c.evidence.row.spectral, "spws"))
    result = build_queue_line_pairs(request(), scan)
    assert result.reasons == ("SPECTRAL_SCAN_NOT_EXPANDED",)
    assert not result.attempts and not result.candidate_enumeration_complete
    c = contexts()[0]
    result = build_queue_line_pairs(replace(request(), intents=("CONTINUUM",)), c)
    assert result.reasons == ("LINE_NOT_SELECTED",) and not result.attempts
    result = build_queue_line_pairs(replace(request(), spectral_windows=()), c)
    assert "NO_PROPOSED_LINE_WINDOWS" in result.reasons and not result.attempts


def test_duplicate_slots_and_result_pairs_are_rejected():
    c = contexts()[0]
    result = build_queue_line_pairs(request(), c)
    with pytest.raises(ValueError):
        replace(result, attempts=(result.attempts[0],) * 2)
    with pytest.raises(ValueError):
        replace(result, candidate_context_id="foreign")
    row = c.evidence.row
    row = replace(row, spectral=replace(row.spectral, spws=(row.spectral.spws[0],) * 2))
    with pytest.raises(ValueError):
        build_queue_line_pairs(request(), replace(c, evidence=replace(c.evidence, row=row)))


def test_cli_strict_json_all_rows_no_network_and_no_overwrite(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network"))
    out = tmp_path / "pairs.json"
    args = ["--request", str(ROOT / "examples/confirmed_line/request.json"),
            "--queue-csv", str(ROOT / "examples/queue_continuum/queue.csv"), "--output", str(out)]
    assert main(args) == 0
    doc = json.loads(out.read_text(), parse_constant=lambda x: pytest.fail(x))
    assert doc["assessment"] == "NOT_EVALUATED"
    assert len(doc["contexts"]) == 4  # Request result_limit=1 cannot truncate preparation.
    assert all(len(c["attempts"]) == 4 for c in doc["contexts"])
    assert "evidence_status" in doc["contexts"][0]["attempts"][0]
    before = out.read_bytes()
    assert main(args) == 2 and out.read_bytes() == before


def test_cli_invalid_csv_and_solar_do_not_emit_report(tmp_path):
    out = tmp_path / "pairs.json"
    bad = tmp_path / "bad.csv"
    bad.write_text("not a queue csv")
    args = ["--request", str(ROOT / "examples/confirmed_line/request.json"),
            "--queue-csv", str(bad), "--output", str(out)]
    assert main(args) == 2 and not out.exists()
    payload = json.loads((ROOT / "examples/confirmed_line/request.json").read_text())
    payload["request"]["target_kind"] = "SUN"
    solar = tmp_path / "solar.json"
    solar.write_text(json.dumps(payload))
    args[1] = str(solar)
    args[3] = str(tmp_path / "does-not-exist.csv")
    assert main(args) == 2 and not out.exists()



def test_cli_rejects_duplicate_json_keys(tmp_path):
    payload = (ROOT / "examples/confirmed_line/request.json").read_text()
    payload = payload.replace(
        '"source_redshift": 0.024',
        '"source_redshift": 0.024,\n    "source_redshift": 0.1',
    )
    request_path = tmp_path / "duplicate.json"
    request_path.write_text(payload)
    out = tmp_path / "pairs.json"
    args = ["--request", str(request_path),
            "--queue-csv", str(ROOT / "examples/queue_continuum/queue.csv"),
            "--output", str(out)]
    assert main(args) == 2
    assert not out.exists()
