"""Candidate execution demo; network access requires --live-archive."""
import argparse
from collections import Counter
import json
from pathlib import Path

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_client import ArchiveClient
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.request_validation import validate_proposed_observation


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-archive", action="store_true")
    parser.add_argument("--queue-csv", type=Path,
                        default=root / "tests/fixtures/queue/queue_pipeline_v1.csv")
    parser.add_argument("--beam-decision-ref", help="Opt into coordinate/formula search with a convention reference")
    args = parser.parse_args()
    payload = json.loads((root / "examples/proposed_observation.json").read_text())
    validation = validate_proposed_observation(payload["request"], payload["search_options"])
    client = ArchiveClient("https://almascience.eso.org/tap") if args.live_archive else None
    result = search_candidates(
        validation, archive_client=client, beam_decision_ref=args.beam_decision_ref,
        queue_loader=lambda: QueueCsvClient().load(args.queue_csv),
    )
    sources = {}
    for source in (result.archive, result.queue):
        sources[source.source] = {
            "status": source.status,
            "input_mode": source.input_mode,
            "processed_rows": len(source.rows),
            "dispositions": dict(Counter(row.disposition for row in source.rows)),
            "filter_outcomes": dict(Counter(f.outcome for row in source.rows for f in row.filters)),
            "requested_filters_fully_evaluated": source.requested_filters_fully_evaluated,
            "omitted_candidate_count": len(source.omitted_candidate_ids),
            "reasons": source.reasons,
        }
    snapshot = getattr(result.queue.source_record, "snapshot", None)
    print(json.dumps({
        "execution": result.execution,
        "spatial_operations": [s.spatial_operation for s in result.plan.sources],
        "retrieval_radius_deg": result.plan.retrieval_radius_deg,
        "beam_decision_ref": result.plan.beam_decision_ref,
        "assessment": result.assessment,
        "sources": sources,
        "queue_source_as_of": str(snapshot.source_as_of) if snapshot else None,
        "total_retained": result.total_retained,
        "shown_candidates": len(result.candidates),
        "truncated": result.truncated,
    }, indent=2))


if __name__ == "__main__":
    main()
