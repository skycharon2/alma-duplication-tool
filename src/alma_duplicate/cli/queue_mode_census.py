"""Run with python -m alma_duplicate.cli.queue_mode_census."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alma_duplicate.queue_mode_census import run_census


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline, provisional per-SPW Queue mode census"
    )
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--require-pinned-snapshot",
        action="store_true",
        help="Reject any bytes other than the repository-pinned 3200-row snapshot",
    )
    args = parser.parse_args(argv)
    try:
        summary = run_census(
            args.queue_csv,
            args.output_dir,
            require_pinned_snapshot=args.require_pinned_snapshot,
        )
    except (OSError, ValueError) as exc:
        print(f"Census failed: {exc}", file=sys.stderr)
        return 2
    print(f"Snapshot SHA256: {summary['snapshot']['sha256']}")
    print(f"Total regular SPWs: {summary['denominator']['regular_spws']}")
    for key in (
        "conditional_unique_configuration",
        "conditional_mode_consensus",
        "reference_only_mode_consensus",
        "source_bound",
    ):
        result = summary[key]
        rate = result["unique_percent"]
        rate_text = "N/A" if rate is None else f"{rate:.6f}%"
        print(
            f"{key}: FDM={result['FDM']} TDM={result['TDM']} UNKNOWN={result['UNKNOWN']} unique={rate_text}"
        )
    print(
        "Conditional BLC signatures are not source-bound Queue mode evidence or a duplication verdict."
    )
    print(f"Report written: {args.output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
