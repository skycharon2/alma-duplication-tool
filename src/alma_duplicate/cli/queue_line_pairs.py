"""Offline Queue line evidence preparation; no duplication assessment."""

import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.cli.json_input import load_request_document
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from alma_duplicate.reporting import json_value
from alma_duplicate.request_validation import validate_proposed_observation


def run(request_path, csv_path):
    _, payload = load_request_document(Path(request_path))
    validation = validate_proposed_observation(payload["request"], payload["search_options"])
    if not validation.is_valid or validation.request is None:
        raise ValueError(f"Invalid request: {validation.issues}")
    if "LINE" not in validation.request.intents:
        raise ValueError("LINE intent required for Queue line preparation")
    if validation.request.target_kind == "SUN":
        raise ValueError("Solar input is exempt; Queue line preparation not applicable")
    parsed = QueueCsvClient().load(csv_path)
    source = build_queue_contexts(parsed)
    if source.status != "COMPLETE":
        raise ValueError(f"Strict Queue context construction failed: {source.reasons}")
    return {
        "report_kind": "QUEUE_LINE_PREPARATION",
        "schema_version": "1",
        "assessment": "NOT_EVALUATED",
        "scope": "ALL_ROWS_IN_SUPPLIED_CSV_NO_SEARCH_FILTERS",
        "snapshot": json_value(parsed.snapshot),
        "request": json_value(validation.request),
        "request_issues": json_value(validation.issues),
        "parser_issues": json_value(parsed.issues),
        "contexts": [json_value(build_queue_line_pairs(validation.request, c)) for c in source.contexts],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.request, args.queue_csv)
        content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        # Exclusive creation prevents accidental replacement of inputs/reports.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"contexts": len(report["contexts"]), "assessment": report["assessment"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
