"""Offline Custom CSV position check; no OT file or candidate binding required."""
import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_custom_backend import assess_queue_custom_csv
from alma_duplicate.queue_custom_science import assess_queue_custom_science
from alma_duplicate.request_validation import validate_proposed_observation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--proposed", type=Path, required=True, help="Fixed ICRS proposed pointing JSON")
    parser.add_argument("--request", type=Path, help="Optional scientific request JSON; enables complete branches")
    parser.add_argument("--nominal-conversion", choices=["PORTAL_SCRIPT_V1"])
    parser.add_argument("--candidate-id", help="Optional exact candidate; default: all Custom groups")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        parsed = parse_queue_csv_bytes(args.queue_csv.read_bytes())
        proposed = json.loads(args.proposed.read_text())
        if args.request is None:
            if args.nominal_conversion is not None:
                raise ValueError("Nominal conversion requires a scientific request")
            result = assess_queue_custom_csv(parsed, proposed, candidate_id=args.candidate_id)
        else:
            payload = json.loads(args.request.read_text())
            if not isinstance(payload, dict):
                raise ValueError("Scientific request file must contain an object")
            validation = validate_proposed_observation(payload.get("request"), payload.get("search_options"))
            if not validation.is_valid or validation.request is None:
                raise ValueError("Invalid scientific request: " + "; ".join(i.code for i in validation.errors))
            result = assess_queue_custom_science(parsed, validation.request, proposed,
                candidate_id=args.candidate_id, nominal_conversion=args.nominal_conversion)
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Custom CSV check failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result["summary"]))
    print(result["scientific_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
