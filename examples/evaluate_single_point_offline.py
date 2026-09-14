"""Synthetic two-source integration example; no live queries or CASE verdicts.

Uses repository test helpers intentionally. Run from a development checkout
with pytest installed. These fixtures verify wiring, not scientific truth.
"""
from dataclasses import asdict, replace
import json

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.search_plan import build_search_plan
from tests.integration.test_candidate_search import queue_rows, interpretations
from tests.integration.test_search_plan_spatial import validation, archive


def build_offline_report():
    validated = validation()
    validated = replace(
        validated,
        search_options=replace(validated.search_options, result_limit=1),
    )
    archive_result, _ = archive(build_search_plan(validated))
    queue_result = queue_rows({}, {"RA": ".1"})
    search = search_candidates(
        validated,
        archive_result=archive_result,
        queue_result=queue_result,
        interpretations=interpretations(queue_result),
    )
    return evaluate_candidate_search(search)


def report_summary(report):
    search = report.search_result
    sources = {}
    for source in (search.archive, search.queue):
        sources[source.source] = {
            "status": source.status,
            "input_mode": source.input_mode,
            "processed_rows": len(source.rows),
            "retained_rows": len(source.retained_rows),
            "omitted_candidate_ids": source.omitted_candidate_ids,
            "reasons": source.reasons,
            "query_binding": (
                source.query_binding.status if source.query_binding else None
            ),
            "requested_filters_fully_evaluated":
                source.requested_filters_fully_evaluated,
        }

    return {
        "evidence_kind": "SYNTHETIC_INTEGRATION_FIXTURE",
        "live_queries_executed": False,
        "evaluation_version": report.evaluation_version,
        "execution": report.execution,
        "assessment": report.assessment,
        "search_assessment": search.assessment,
        "sources": sources,
        "total_retained": search.total_retained,
        "shown_candidates": len(search.candidates),
        "evaluated_contexts": len(report.context_evaluations),
        "search_display_truncated": search.truncated,
        "request_criteria": [asdict(r) for r in report.request_criteria],
        "context_evaluations": [
            {
                "context_id": item.candidate.context.context_id,
                "reference": asdict(item.candidate.context.reference),
                "alternative_context_ids":
                    item.candidate.context.alternative_context_ids,
                "disposition": item.candidate.disposition,
                "filters": [
                    {
                        "name": f.name,
                        "outcome": f.outcome,
                        "reasons": f.reasons,
                    }
                    for f in item.candidate.filters
                ],
                "criteria": [asdict(r) for r in item.criteria],
            }
            for item in report.context_evaluations
        ],
    }


if __name__ == "__main__":
    print(json.dumps(
        report_summary(build_offline_report()),
        indent=2,
        allow_nan=False,
    ))
