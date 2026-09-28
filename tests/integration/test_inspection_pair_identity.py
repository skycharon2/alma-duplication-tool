"""Four real evaluator pairs must survive the report inspection boundary."""
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.reporting import report_document
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_line_preparation import payload, validate


def test_missing_planned_rms_on_four_queue_spws_is_not_collapsed():
    p = payload()
    p["search_options"]["sources"] = ["QUEUE"]
    p["request"]["spectral_windows"][0]["center"].update(value=230, kind="SKY")
    p["request"]["sensitivities"][0].pop("rms")
    row = {"Project Code": "2025.1.00001.S", "RA": "201.365", "Dec": "-43.019",
           "Use 7-m?": "False", "Use TP?": "False", "Polarization": "DOUBLE",
           "Req. Ang. Res.": "0.3", "Velocity": "0", "Long Offset": "0", "Lat Offset": "0"}
    for number in range(1, 5):
        row.update({f"Freq SPW {number}": "230", f"Bandwidth SPW {number}": "1875",
                    f"Spec.Res. SPW {number}": "0.9765625"})
    validated = validate(p)
    assert validated.is_valid
    document = report_document(evaluate_candidate_search(
        search_candidates(validated, queue_result=queue_rows(row)), queue_line=True))
    assert len(document["context_evaluations"][0]["line_pairs"]) == 4
    view = inspect_report(document)
    occurrences = [o for o in view["gap_occurrences"]
                   if o["code"] == "PLANNED_LINE_RMS_REQUIRED" and "pair_identity" in o]
    assert len(occurrences) == 4
    assert {o["pair_identity"]["reference"]["spw_number"] for o in occurrences} == {1, 2, 3, 4}
    legacy = inspect_report(document, inspection_version="2")
    assert len([o for o in legacy["gap_occurrences"]
                if o["code"] == "PLANNED_LINE_RMS_REQUIRED" and "/line_pairs/" in o["location"]]) == 1
