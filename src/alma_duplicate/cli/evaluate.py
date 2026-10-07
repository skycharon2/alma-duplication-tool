"""Evaluate a request file and export scoped criterion and branch results."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, AssessmentStatus, assess_observation,
)
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.cli.json_input import load_request_document
from alma_duplicate.reporting import json_value, write_report
from alma_duplicate.rules.continuum_setup import PORTAL_SCRIPT_V1


def main(argv=None, *, archive_client_factory=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--queue-csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    archive_input = parser.add_mutually_exclusive_group()
    archive_input.add_argument("--live-archive", action="store_true")
    archive_input.add_argument("--archive-replay", type=Path, help="Replay a captured TAP manifest offline")
    parser.add_argument("--archive-array-evidence", type=Path,
                        help="Bind captured official AQ source array labels using their manifest")
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
    parser.add_argument('--nominal-conversion', choices=(PORTAL_SCRIPT_V1, 'NONE'),
                        default=PORTAL_SCRIPT_V1,
                        help='Proposed continuum nominal-to-usable mapping; NONE retains unconverted evidence')
    args = parser.parse_args(argv)

    try:
        if args.archive_array_evidence is not None and not (args.archive_replay or args.live_archive):
            raise ValueError("--archive-array-evidence requires --archive-replay or --live-archive")
        inputs = [args.request]
        if args.archive_array_evidence is not None:
            inputs.append(args.archive_array_evidence)
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

        def archive_provider():
            catalog = None
            if args.archive_array_evidence is not None:
                from alma_duplicate.archive_array_evidence import load_archive_array_catalog
                catalog = load_archive_array_catalog(args.archive_array_evidence)
                if args.output.resolve() in catalog.input_paths:
                    raise ValueError("Output must not replace an array evidence response")
            if args.archive_replay is not None:
                from alma_duplicate.clients.archive_replay import RecordedArchiveClient
                client = RecordedArchiveClient(args.archive_replay)
                if args.output.resolve() in client.input_paths:
                    raise ValueError("Output must not replace a replay response")
                return ArchiveInput(client, client.metadata, catalog)
            factory = archive_client_factory
            if factory is None:
                from alma_duplicate.clients.archive_client import ArchiveClient
                factory = lambda: ArchiveClient("https://almascience.eso.org/tap")
            return ArchiveInput(factory(), array_catalog=catalog)

        archive_kind = "REPLAY" if args.archive_replay is not None else "LIVE" if args.live_archive else None
        loader = (lambda: QueueCsvClient().load(args.queue_csv)) if args.queue_csv is not None else None
        result = assess_observation(
            payload["request"], payload["search_options"],
            options=AssessmentOptions(
                beam_decision_ref=args.beam_decision_ref,
                queue_candidate_beam=args.queue_candidate_beam,
                aq_equivalent_filters=args.aq_equivalent_filters,
                queue_common=args.queue_common,
                queue_continuum=args.queue_continuum,
                queue_line=args.queue_line,
                nominal_conversion=None if args.nominal_conversion == 'NONE' else args.nominal_conversion,
            ),
            sources=AssessmentSources(archive_kind, archive_provider if archive_kind else None, loader),
            input_sha256=hashlib.sha256(raw).hexdigest(),
        )
        if result.status == AssessmentStatus.REQUEST_NOT_SEARCH_READY:
            print(json.dumps({
                "error": "REQUEST_NOT_SEARCH_READY",
                "issues": json_value(result.validation.issues),
                "search_readiness": result.validation.search_readiness,
            }, allow_nan=False), file=sys.stderr)
            return 2
        if result.status == AssessmentStatus.SOLAR_EXEMPTION:
            if args.overwrite and (args.archive_replay is not None or args.archive_array_evidence is not None):
                raise ValueError("Solar exemption with Archive evidence requires a new output (no --overwrite)")
            write_report(args.output, result.document, overwrite=args.overwrite)
            print(f"Solar exemption report written: {args.output}")
            return 0
        document = result.document
        write_report(args.output, document, overwrite=args.overwrite)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 2

    print(f"Report written: {args.output}")
    return 3 if result.status == AssessmentStatus.SOURCES_UNAVAILABLE else 0


if __name__ == "__main__":
    raise SystemExit(main())
