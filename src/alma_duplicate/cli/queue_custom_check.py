"""Offline Custom CSV position check; no OT file or candidate binding required."""
import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_custom_backend import assess_queue_custom_csv


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--proposed", type=Path, required=True, help="Fixed ICRS proposed pointing JSON")
    parser.add_argument("--candidate-id", help="Optional exact candidate; default: all Custom groups")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        parsed = parse_queue_csv_bytes(args.queue_csv.read_bytes())
        proposed = json.loads(args.proposed.read_text())
        result = assess_queue_custom_csv(parsed, proposed, candidate_id=args.candidate_id)
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Custom CSV check failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result["summary"]))
    print("Provisional CSV position model; complete duplication is not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
