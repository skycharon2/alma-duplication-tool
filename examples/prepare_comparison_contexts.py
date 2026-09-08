"""Offline Queue contexts; Archive is explicitly not provided."""
import json
from pathlib import Path

from alma_duplicate.comparison import prepare_comparison
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.request_validation import validate_proposed_observation


def main():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "examples/proposed_observation.json").read_text())
    validation = validate_proposed_observation(payload["request"], payload["search_options"])
    parsed = parse_queue_csv_bytes(
        (root / "tests/fixtures/queue/queue_pipeline_v1.csv").read_bytes()
    )
    result = prepare_comparison(validation, queue=parsed)
    print(json.dumps({
        "archive_status": result.archive.status,
        "queue_status": result.queue.status,
        "queue_context_count": len(result.queue.contexts),
        "queue_source_as_of": str(parsed.snapshot.source_as_of),
        "search_execution": result.search_execution,
        "assessment": result.assessment,
        "first_context_reasons": result.queue.contexts[0].reasons if result.queue.contexts else (),
    }, indent=2))


if __name__ == "__main__":
    main()
