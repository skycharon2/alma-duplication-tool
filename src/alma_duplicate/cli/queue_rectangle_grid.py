"""Offline Mosaic reconstruction: python -m alma_duplicate.cli.queue_rectangle_grid."""

import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_rectangle_grid import reconstruct_queue_rectangles


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit Queue Rectangle geometry candidates; no duplication verdict")
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New JSON file; never overwritten")
    args = parser.parse_args(argv)
    try:
        parsed = parse_queue_csv_bytes(args.queue_csv.read_bytes(),
                                       source_url=args.queue_csv.resolve().as_uri())
        report = reconstruct_queue_rectangles(parsed)
        content = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content)
    except (OSError, ValueError) as exc:
        print(f"Queue Rectangle geometry reconstruction failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report["summary"], ensure_ascii=False))
    print("Reconstruction only; duplication criteria have not been evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
