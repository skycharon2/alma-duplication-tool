"""Evaluate a request file and export scoped criterion and branch results."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.cli.json_input import load_request_document
from alma_duplicate.reporting import json_value, report_document, write_report
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.evaluation_model import SolarExemptionReport



def main(argv=None, *, archive_client_factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--queue-csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    archive_input = parser.add_mutually_exclusive_group()
    archive_input.add_argument("--live-archive", action="store_true")
    archive_input.add_argument("--archive-replay", type=Path, help="Replay a captured TAP manifest offline")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--beam-decision-ref")
    parser.add_argument("--queue-candidate-beam", action="store_true",
                        help="Use the source-documented Queue candidate-frequency beam profile")
    parser.add_argument("--aq-equivalent-filters", action="store_true")
    parser.add_argument("--queue-common", action="store_true",
                        help="Evaluate Queue row-beam position and independently scoped angular rules")
    parser.add_argument("--queue-continuum", action="store_true",
                        help="Evaluate scoped Queue continuum; includes Queue common rules")
    parser.add_argument("--queue-line", action="store_true",
                        help="Evaluate fixed single-field regular-SPW Queue LINE pairs")
    args = parser.parse_args(argv)

    try:
        inputs = [args.request]
        if args.queue_csv is not None:
            inputs.append(args.queue_csv)
        if args.archive_replay is not None:
            inputs.append(args.archive_replay)
        if any(args.output.resolve() == p.resolve() for p in inputs):
            raise ValueError("Output must not replace an input file")
        if args.output.exists() and not args.overwrite:
            raise FileExistsError(
                "Output exists; select another path or use --overwrite"
            )
        raw, payload = load_request_document(args.request)
        validated = validate_proposed_observation(
            payload["request"], payload["search_options"]
        )
        if validated.is_valid and validated.request.target_kind == "SUN":
            # No client, replay manifest or Queue file is opened for an exempt request.
            # Without reading a replay manifest, its referenced response paths are unknown.
            if args.overwrite and args.archive_replay is not None:
                raise ValueError("Solar exemption with --archive-replay requires a new output (no --overwrite)")
            document = report_document(
                SolarExemptionReport(validation=validated),
                input_sha256=hashlib.sha256(raw).hexdigest(),
            )
            write_report(args.output, document, overwrite=args.overwrite)
            print(f"Solar exemption report written: {args.output}")
            return 0
        if not validated.is_valid or not validated.can_search:
            print(json.dumps({
                "error": "REQUEST_NOT_SEARCH_READY",
                "issues": json_value(validated.issues),
                "search_readiness": validated.search_readiness,
            }, allow_nan=False), file=sys.stderr)
            return 2

        selected = validated.search_options.sources
        if (args.queue_common or args.queue_continuum or args.queue_line) and "QUEUE" not in selected:
            raise ValueError("--queue-common/--queue-continuum/--queue-line requires QUEUE selection")
        if args.queue_line and "LINE" not in validated.request.intents:
            raise ValueError("--queue-line requires LINE intent")
        if args.live_archive and "ARCHIVE" not in selected:
            raise ValueError("--live-archive requires ARCHIVE selection")
        if args.queue_csv is not None and "QUEUE" not in selected:
            raise ValueError("--queue-csv requires QUEUE selection")
        if args.beam_decision_ref is not None and not args.beam_decision_ref.strip():
            raise ValueError("--beam-decision-ref must not be blank")

        replay_metadata = None
        client = None
        if args.archive_replay is not None:
            if "ARCHIVE" not in selected:
                raise ValueError("--archive-replay requires ARCHIVE selection")
            from alma_duplicate.clients.archive_replay import RecordedArchiveClient
            client = RecordedArchiveClient(args.archive_replay)
            if args.output.resolve() in client.input_paths:
                raise ValueError("Output must not replace a replay response")
            replay_metadata = client.metadata
        if args.live_archive:
            if archive_client_factory is None:
                from alma_duplicate.clients.archive_client import ArchiveClient
                archive_client_factory = lambda: ArchiveClient(
                    "https://almascience.eso.org/tap"
                )
            client = archive_client_factory()

        loader = None
        if args.queue_csv is not None:
            loader = lambda: QueueCsvClient().load(args.queue_csv)
        search = search_candidates(
            validated,
            archive_client=client,
            queue_loader=loader,
            beam_decision_ref=args.beam_decision_ref,
            aq_equivalent_filters=args.aq_equivalent_filters,
            queue_candidate_beam=args.queue_candidate_beam,
        )
        # Archive fixed-celestial interpretation is versioned in its criterion.
        # Queue interpretation is selected only by the explicit common-method option.
        report = evaluate_candidate_search(search, queue_common=args.queue_common,
                                           queue_continuum=args.queue_continuum,
                                           queue_line=args.queue_line)
        document = report_document(
            report, input_sha256=hashlib.sha256(raw).hexdigest(),
            archive_replay_metadata=replay_metadata
        )
        write_report(args.output, document, overwrite=args.overwrite)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 2

    unavailable = any(
        source.status in {"FAILED", "INCOMPLETE", "NOT_PROVIDED"}
        for source in (search.archive, search.queue)
    )
    print(f"Report written: {args.output}")
    return 3 if unavailable else 0


if __name__ == "__main__":
    raise SystemExit(main())
