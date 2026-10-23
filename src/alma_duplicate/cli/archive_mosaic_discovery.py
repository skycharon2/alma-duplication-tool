"""Capture the visible science Mosaic execution inventory for one Member/target."""
import argparse
from pathlib import Path

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.archive_mosaic_discovery import capture_inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--member', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--origin', choices=ARCHIVE_ORIGINS, default=ARCHIVE_ORIGINS[0])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = capture_inventory(args.output_dir, member=args.member, source=args.source, origin=args.origin)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Inventory capture failed: {exc}\n')
    print(f"{receipt['status']}: {args.output_dir}")
    return 0 if receipt['status'] == 'CAPTURED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
