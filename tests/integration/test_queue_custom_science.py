"""Source-bound complete Custom branches reuse Queue numerics and array OR."""
from dataclasses import replace
import json

import pytest

from alma_duplicate.cli.queue_custom_check import main
from alma_duplicate.queue_custom_science import assess_queue_custom_science, aggregate_custom_arrays
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.aggregation import BranchAssessment, Truth
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_confirmed_continuum import payload
from tests.integration.test_queue_line_evaluation import request as line_request


def candidate(changes=None, *, rows=2):
    base = {"Mosaic": "Custom", "RA": "201.365", "Dec": "-43.019", "Mos. Coord.": "ICRS",
        "Use 7-m?": "True", "Use TP?": "True", "Req. Ang. Res.": ".45",
        "Ref.Frequency": "230", "Ref.Freq.Width": "7500", "Req.Sensitivity": ".15", "Velocity": "0"}
    for n, center in enumerate((226, 228, 232, 234), 1):
        base.update({f"Freq SPW {n}": str(center), f"Bandwidth SPW {n}": "1875"})
    return queue_rows(*[base | {"Long Offset": str(i*2), "Lat Offset": "0"} | (changes or {}) for i in range(rows)])


def request():
    p = payload()
    p["request"]["geometry"] = "MOSAIC"
    p["request"]["representative_frequency"]["value"] = 230
    p["request"]["sensitivities"][0]["rms"]["value"] = .1
    v = validate_proposed_observation(p["request"], p["search_options"])
    assert v.is_valid, v.issues
    return v.request, p


def pointings(req, *, ra=201.365, basis="PER_POINTING", complete=True):
    return dict(source_name=req.target_name, setup_id=req.setup_id,
        sensitivity_basis=basis, frame_basis="USER_CONFIRMED_FIXED_ICRS",
        completeness="USER_CONFIRMED_COMPLETE" if complete else "NOT_CONFIRMED",
        points=[dict(id="p", ra_deg=ra, dec_deg=-43.019, frame="ICRS")])


def science(result):
    return result["candidates"][0]["science"]


def rule(variant, name):
    return next(c for c in variant["criteria"] if c["criterion_id"] == name)


def test_both_inferred_arrays_return_independent_complete_matches():
    req, _ = request()
    result = assess_queue_custom_science(candidate(), req, pointings(req))
    s = science(result)
    assert [v["diameter_m"] for v in s["variants"]] == [7., 12.]
    assert [v["branches"][0]["truth"] for v in s["variants"]] == ["TRUE", "TRUE"]
    assert s["branches"][0]["truth"] == "TRUE"
    assert s["matching_arrays_by_intent"]["CONTINUUM"] == [7., 12.]
    assert rule(s["variants"][1], "CONT-RMS")["candidate"]["value"] == .15
    assert dict(rule(s["variants"][1], "CONT-RMS")["details"])["mosaic_overlap_gain"] == "NONE"
    json.dumps(result, allow_nan=False)


def test_frequency_failure_can_resolve_both_branches_without_known_position():
    req, _ = request()
    result = assess_queue_custom_science(candidate({"Ref.Frequency": "100"}), req, pointings(req))
    assert science(result)["branches"][0]["truth"] == "FALSE"
    assert science(result)["matching_arrays_by_intent"]["CONTINUUM"] == []


def test_omitted_rms_basis_defaults_to_per_pointing():
    req, _ = request()
    p = pointings(req)
    del p['sensitivity_basis']
    s = science(assess_queue_custom_science(candidate(), req, p))
    assert s['matching_arrays_by_intent']['CONTINUUM'] == [7., 12.]


@pytest.mark.parametrize("basis", [None, "COMBINED_IMAGE"])
def test_combined_or_missing_mosaic_rms_basis_is_not_assumed(basis):
    req, _ = request()
    s = science(assess_queue_custom_science(candidate(), req, pointings(req, basis=basis)))
    assert s["branches"][0]["truth"] == "UNKNOWN"
    assert rule(s["variants"][1], "CONT-RMS")["outcome"] is None
    assert rule(s["variants"][1], "CONT-FREQ")["outcome"] == "SATISFIED"


def test_pointing_scope_and_source_identity_do_not_leak():
    req, _ = request()
    assert science(assess_queue_custom_science(candidate(), req, pointings(req, complete=False)))["branches"][0]["truth"] == "UNKNOWN"
    assert science(assess_queue_custom_science(candidate(), req, pointings(req, ra=0)))["branches"][0]["truth"] == "FALSE"
    for field in ("source_name", "setup_id"):
        p = pointings(req); p[field] = "other"
        with pytest.raises(ValueError, match="target and setup"):
            assess_queue_custom_science(candidate(), req, p)


def test_single_array_and_same_group_duplicates_do_not_improve_rms():
    req, _ = request()
    one = science(assess_queue_custom_science(candidate({"Use 7-m?": "False"}, rows=1), req, pointings(req)))
    multiple = science(assess_queue_custom_science(candidate({"Use 7-m?": "False"}, rows=3), req, pointings(req)))
    assert len(one["variants"]) == len(multiple["variants"]) == 1
    assert rule(one["variants"][0], "CONT-RMS")["derived"] == rule(multiple["variants"][0], "CONT-RMS")["derived"]


def test_whole_branch_or_and_identity_validation():
    required = ("POS-MOSAIC", "ANGULAR", "CONT-SETUP", "CONT-FREQ", "CONT-RMS")
    def branch(truth):
        return BranchAssessment("CONTINUUM", "c", {Truth.TRUE:"CRITERIA_MET",Truth.FALSE:"CRITERIA_NOT_MET",Truth.UNKNOWN:"INDETERMINATE"}[truth], truth, required)
    # Both complete branches fail, even if different individual criteria passed.
    variants = [dict(diameter_m=7., branches=[branch(Truth.FALSE)]), dict(diameter_m=12., branches=[branch(Truth.FALSE)])]
    assert aggregate_custom_arrays("c", (7.,12.), variants)[0].truth is Truth.FALSE
    variants[1]["branches"] = [branch(Truth.TRUE)]
    assert aggregate_custom_arrays("c", (7.,12.), variants)[0].truth is Truth.TRUE
    variants[1]["branches"] = [replace(branch(Truth.TRUE), context_id="foreign")]
    with pytest.raises(ValueError, match="source context"):
        aggregate_custom_arrays("c", (7.,12.), variants)


def test_line_reuses_same_spw_rules_and_returns_complete_12m_match():
    req = replace(line_request(center_ghz=226., resolution_kms=20), geometry="MOSAIC")
    p = pointings(req)
    result = assess_queue_custom_science(candidate({"Project Code": "2024.1.00001.S", "Polarization": "DOUBLE", "Req.Sensitivity": "0.001", "Spec.Res. SPW 1": "0.9765625"}), req, p)
    s = science(result)
    assert s["matching_arrays_by_intent"]["LINE"] == [7., 12.]
    pairs = s["variants"][1]["line_pairs"]
    passing = [pair for pair in pairs if pair["truth"] == "TRUE"]
    assert passing and all(pair["reference"]["spw_number"] == 1 for pair in passing)
    assert all(pair["criteria"][0]["criterion_id"] == "POS-MOSAIC" for pair in pairs)
    assert s["variants"][0]["branches"][0]["truth"] == "TRUE"


def test_line_cannot_borrow_coverage_and_mode_from_different_spws():
    req = replace(line_request(center_ghz=226., resolution_kms=20), geometry="MOSAIC")
    result = assess_queue_custom_science(candidate({"Project Code": "2024.1.00001.S", "Polarization": "DOUBLE", "Req.Sensitivity": "0.001", "Spec.Res. SPW 1": "31.25"}), req, pointings(req))
    s = science(result)
    assert s["matching_arrays_by_intent"]["LINE"] == []
    assert s["branches"][0]["truth"] == "FALSE"


def test_cli_science_mode_roundtrip_and_invalid_request(tmp_path):
    req, p = request()
    parsed = candidate()
    source = tmp_path / "source.csv"
    # Preserve the parser's source bytes via its complete retained text.
    from tests.unit.test_queue_csv_parser import _records, _render
    records = _records()[:41]
    for row in parsed.raw_rows:
        records.append(list(row.raw_values))
    source.write_bytes(_render(records))
    rp, pp, out = (tmp_path / name for name in ("request.json", "proposed.json", "report.json"))
    rp.write_text(json.dumps(p)); pp.write_text(json.dumps(pointings(req)))
    args = ["--queue-csv", str(source), "--request", str(rp), "--proposed", str(pp), "--output", str(out)]
    assert main(args) == 0
    before = out.read_bytes()
    assert science(json.loads(before))["matching_arrays_by_intent"]["CONTINUUM"] == [7., 12.]
    assert main(args) == 2 and out.read_bytes() == before
    rp.write_text("[]")
    assert main(args) == 2


@pytest.mark.parametrize("convention,sky", [("RADIO",False),("OPTICAL",False),("RELATIVISTIC",False),("RADIO",True)])
def test_existing_velocity_conversion_is_reused_once_and_frame_retained(convention, sky):
    import math
    req, _ = request()
    result = assess_queue_custom_science(candidate({"Velocity":"300", "Vel. Frame":"lsrk",
        "Vel. Convention":convention, "Is Sky Freq?":str(sky)}), req, pointings(req))
    rms = rule(science(result)["variants"][1], "CONT-RMS")
    records = json.loads(dict(rms["details"])["spw_evidence_json"])
    beta = 300/299792.458
    factor = 1 if sky else {"RADIO":1-beta, "OPTICAL":1/(1+beta),
                            "RELATIVISTIC":math.sqrt((1-beta)/(1+beta))}[convention]
    assert records[0]["sky_frequency_ghz"] == pytest.approx(226*factor)
    assert records[0]["doppler_factor"] == pytest.approx(factor)
    assert records[0]["velocity_frame"] == "lsrk"
    assert records[0]["velocity_convention"] == convention


def test_line_rms_basis_and_proposed_enumeration_stay_independent():
    req = replace(line_request(center_ghz=226., resolution_kms=20), geometry="MOSAIC")
    q = candidate({"Project Code":"2024.1.00001.S", "Polarization":"DOUBLE",
        "Req.Sensitivity":"0.001", "Spec.Res. SPW 1":"0.9765625"})
    s = science(assess_queue_custom_science(q, req, pointings(req, basis=None)))
    assert s["branches"][0]["truth"] == "UNKNOWN"
    req = replace(req, setup_complete=False)
    # An unresolved enumeration must not erase an actual complete passing pair.
    s = science(assess_queue_custom_science(q, req, pointings(req)))
    assert s["branches"][0]["truth"] == "TRUE"


def test_spectral_budget_fails_before_partial_scientific_report(monkeypatch):
    req, _ = request()
    monkeypatch.setattr("alma_duplicate.queue_custom_science.MAX_SPECTRAL_PAIRS", 1)
    with pytest.raises(ValueError, match="spectral pair budget"):
        assess_queue_custom_science(candidate(), req, pointings(req))


def test_custom_science_does_not_relax_legacy_single_point_scope():
    from alma_duplicate.comparison import build_queue_contexts
    from alma_duplicate.rules.queue_common import queue_common_scope_supported
    from alma_duplicate.queue_line_pairing import build_queue_line_pairs
    req = replace(line_request(), geometry="MOSAIC")
    context = build_queue_contexts(candidate()).contexts[0]
    legacy = build_queue_line_pairs(req, context)
    assert "QUEUE_SINGLE_FIELD_REQUIRED" in legacy.reasons
    assert "FIXED_SINGLE_POINT_REQUEST_REQUIRED" in legacy.reasons
    from alma_duplicate.queue_custom_science import _common
    from alma_duplicate.queue_custom_backend import assess_queue_custom_csv
    p = assess_queue_custom_csv(candidate(), pointings(req))["candidates"][0]["position"]["beam_variants"][1]
    common = _common(req, context, p)
    assert queue_common_scope_supported(common, mosaic=True)
    assert not queue_common_scope_supported(common)


def test_complementary_array_successes_cannot_be_borrowed(monkeypatch):
    import alma_duplicate.queue_custom_science as backend
    from alma_duplicate.rules.model import CriterionOutcome as O, EvaluationStatus as E, MethodApplicability as A
    req, _ = request()
    original_common, original_continuum = backend._common, backend.evaluate_queue_continuum
    def common(request, context, position):
        angular, spatial = original_common(request, context, position)
        spatial = replace(spatial, outcome=O.SATISFIED if position['diameter_m']==7 else O.NOT_SATISFIED,
                          applicability=A.APPLICABLE, evaluation=E.EVALUATED, issues=())
        return angular, spatial
    def continuum(request, context, common, **kwargs):
        frequency, rms = original_continuum(request, context, common, **kwargs)
        diameter = dict(common[1].derived)['antenna_diameter_m']
        rms = replace(rms, outcome=O.NOT_SATISFIED if diameter==7 else O.SATISFIED)
        return frequency, rms
    monkeypatch.setattr(backend, '_common', common)
    monkeypatch.setattr(backend, 'evaluate_queue_continuum', continuum)
    s = science(backend.assess_queue_custom_science(candidate(), req, pointings(req)))
    assert [v['branches'][0]['truth'] for v in s['variants']] == ['FALSE','FALSE']
    assert s['branches'][0]['truth'] == 'FALSE'
    assert s['matching_arrays_by_intent']['CONTINUUM'] == []


def test_7m_only_spatial_hit_returns_match_when_12m_fails():
    from alma_duplicate.geometry import primary_beam_fwhm_deg
    req, _ = request()
    p = pointings(req)
    r7 = primary_beam_fwhm_deg(230, 7)/2
    r12 = primary_beam_fwhm_deg(230, 12)/2
    p['points'][0]['dec_deg'] += (r7+r12)/2
    result = assess_queue_custom_science(candidate(), req, p)
    s = science(result)
    assert [v['outcome'] for v in result['candidates'][0]['position']['beam_variants']] == ['SATISFIED','NOT_SATISFIED']
    assert [v['branches'][0]['truth'] for v in s['variants']] == ['TRUE','FALSE']
    assert s['branches'][0]['truth'] == 'TRUE'
    assert s['matching_arrays_by_intent']['CONTINUUM'] == [7.]
