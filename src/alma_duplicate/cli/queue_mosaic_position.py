"""Position-only Queue Mosaic evaluation with explicit array coverage bindings."""

import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.rules.queue_mosaic_position import QueueMosaicCoverage, assess_queue_mosaic_position


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate bound Queue Mosaic position evidence only")
    parser.add_argument("--reconstruction", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--proposed", type=Path, required=True, help="JSON from cli.proposed_mosaic")
    parser.add_argument("--coverage", type=Path, required=True, help="JSON array of explicit coverage bindings")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        reconstruction = json.loads(args.reconstruction.read_text())
        proposed = json.loads(args.proposed.read_text())
        raw = json.loads(args.coverage.read_text())
        if not isinstance(raw, list):
            raise ValueError("Coverage file must contain a JSON array")
        coverages = [QueueMosaicCoverage(**entry) for entry in raw]
        report = assess_queue_mosaic_position(proposed, reconstruction, args.candidate_id, coverages)
        content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(content)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Queue Mosaic position failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps([{k: v[k] for k in ("diameter_m", "outcome", "counts")}
                      for v in report["beam_variants"]]))
    print("Position only; complete duplication branches have not been evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
