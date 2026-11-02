"""Produce Custom coverage and an OT parity audit directly from CSV."""
import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_mosaic_binding import CustomOTBinding, bind_custom_ot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--ot-pointings", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True, help="CustomOTBinding JSON; no coordinates")
    parser.add_argument("--tolerance-arcsec", type=float, default=0.001)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        binding = CustomOTBinding(**json.loads(args.binding.read_text()))
        parsed = parse_queue_csv_bytes(args.queue_csv.read_bytes())
        report = bind_custom_ot(parsed, args.ot_pointings.read_bytes(), binding,
                                tolerance_arcsec=args.tolerance_arcsec)
        content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Queue Custom binding failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: report[k] for k in ("status", "parity_status", "reasons")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
