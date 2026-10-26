"""Capture or replay bounded s_region Mosaic acceptance through the main entry."""

import argparse
import json
from pathlib import Path

from alma_duplicate.mosaic_region_acceptance import run_acceptance
from alma_duplicate.proposed_mosaic import import_proposed
from alma_duplicate.parsers.ot_pointings import MAX_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument(
        "--replay", type=Path, help="Sealed capture directory from a previous run"
    )
    parser.add_argument("--request", type=Path)
    parser.add_argument("--pointings", type=Path)
    parser.add_argument("--array", choices=("7m", "12m"))
    parser.add_argument("--confirm-fixed-icrs", action="store_true")
    parser.add_argument("--confirm-complete", action="store_true")
    parser.add_argument("--member", action="append", default=[])
    parser.add_argument("--margin-arcsec", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = proposed = None
        if args.live:
            if not all(
                (
                    args.request,
                    args.pointings,
                    args.array,
                    args.member,
                    args.confirm_fixed_icrs,
                    args.confirm_complete,
                )
            ):
                raise ValueError(
                    "Live acceptance requires request, pointings, array, Members and both confirmations"
                )
            request = json.loads(args.request.read_text())
            with args.pointings.open("rb") as stream:
                proposed = import_proposed(
                    stream.read(MAX_BYTES + 1),
                    source_name=request["request"]["target_name"],
                    array=args.array,
                    confirm_fixed_icrs=True,
                    confirm_complete=True,
                )
        elif any((args.request, args.pointings, args.array, args.member)):
            raise ValueError(
                "Replay uses captured inputs; omit request, pointings, array and Members"
            )
        summary = run_acceptance(
            args.output_dir,
            request=request,
            proposed=proposed,
            members=args.member,
            replay=args.replay,
            margin_arcsec=args.margin_arcsec,
        )
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"{exc}\n")
    print(f"{summary['assessment_status']}: {args.output_dir / 'summary.json'}")
    return 0 if summary["assessment_status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
