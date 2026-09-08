"""Offline plan and Queue spatial evidence; no network or invented frame policy."""
import json
from pathlib import Path
from collections import Counter

from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import build_search_plan
from alma_duplicate.spatial import adapt_spatial


def main():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples/proposed_observation.json").read_text())
    validation = validate_proposed_observation(payload["request"], payload["search_options"])
    plan = build_search_plan(validation)
    parsed = parse_queue_csv_bytes(
        (root / "tests/fixtures/queue/queue_pipeline_v1.csv").read_bytes()
    )
    contexts = build_queue_contexts(parsed).contexts
    evidence = [adapt_spatial(c, parsed) for c in contexts]
    print(json.dumps({
        "plan_version": plan.version,
        "execution": plan.execution,
        "sources": [
            {"source": s.source, "spatial_operation": s.spatial_operation,
             "predicates": [{"name": p.name, "action": p.action, "reason": p.reason}
                            for p in s.predicates]}
            for s in plan.sources
        ],
        "queue_spatial_status_counts": dict(Counter(e.selection_status for e in evidence)),
        "queue_source_as_of": str(parsed.snapshot.source_as_of),
        "assessment": "NOT_EVALUATED",
    }, indent=2))


if __name__ == "__main__":
    main()
