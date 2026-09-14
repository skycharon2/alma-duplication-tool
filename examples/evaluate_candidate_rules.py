"""Offline Queue candidate search followed by provisional criterion evaluation."""
import json
from dataclasses import asdict
from pathlib import Path

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.evaluation import evaluate_candidate_search


def main():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples/proposed_observation.json").read_text())
    validation = validate_proposed_observation(payload["request"], payload["search_options"])
    result = search_candidates(validation, queue_loader=lambda: QueueCsvClient().load(
        root / "tests/fixtures/queue/queue_pipeline_v1.csv"))
    report = evaluate_candidate_search(result)
    snapshot = result.queue.source_record.snapshot
    print(json.dumps({
        "evaluation_version": report.evaluation_version,
        "execution": report.execution,
        "assessment": report.assessment,
        "search_assessment": result.assessment,
        "source_statuses": {s.source: {"status": s.status, "reasons": s.reasons}
                            for s in (result.archive, result.queue)},
        "queue_source_as_of": str(snapshot.source_as_of),
        "search_display_truncated": result.truncated,
        "shown_candidates": len(result.candidates),
        "evaluated_contexts": len(report.context_evaluations),
        "request_criteria": [asdict(r) for r in report.request_criteria],
        "context_evaluations": [{
            "source": e.candidate.context.reference.source,
            "context_id": e.candidate.context.context_id,
            "disposition": e.candidate.disposition,
            "filters": [{"name": f.name, "outcome": f.outcome, "reasons": f.reasons}
                        for f in e.candidate.filters],
            "criteria": [asdict(r) for r in e.criteria],
        } for e in report.context_evaluations],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
