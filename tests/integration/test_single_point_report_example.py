"""Verify the offline report example without treating fixtures as CASE truth."""
import json

from examples.evaluate_single_point_offline import (
    build_offline_report, report_summary,
)


def test_two_sources_and_display_limit_preserve_full_evaluation():
    report = build_offline_report()
    summary = report_summary(report)
    assert summary["evidence_kind"] == "SYNTHETIC_INTEGRATION_FIXTURE"
    assert summary["live_queries_executed"] is False
    assert summary["sources"]["ARCHIVE"]["status"] == "COMPLETED"
    assert summary["sources"]["QUEUE"]["status"] == "COMPLETED"
    assert summary["shown_candidates"] == 1
    assert summary["search_display_truncated"] is True
    assert summary["evaluated_contexts"] == summary["total_retained"] == 3
    assert len(report.request_criteria) == 1
    assert report.request_criteria[0].criterion_id == "CONT-SETUP"


def test_serializable_report_preserves_provenance_and_provisional_boundary():
    report = build_offline_report()
    summary = report_summary(report)
    decoded = json.loads(json.dumps(summary, allow_nan=False))
    assert decoded["assessment"] == "NOT_AGGREGATED"
    assert decoded["search_assessment"] == "NOT_EVALUATED"
    for item in report.context_evaluations:
        assert item.candidate.context.reference.raw_row_id
        assert item.candidate.context.reference.source_record_id
        assert item.criteria[0].criterion_id == "ANGULAR"
        assert item.criteria[0].context_id == item.candidate.context.context_id
        assert not item.criteria[0].eligible_for_formal_aggregation
    for item in decoded["context_evaluations"]:
        assert item["reference"]["source"] in {"ARCHIVE", "QUEUE"}
        assert item["criteria"][0]["approval"] == "PROVISIONAL"
