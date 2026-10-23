"""Acquire and inspect a selected auxiliary package for execution-local listobs."""
import argparse
from pathlib import Path

from alma_duplicate.archive_auxiliary import acquire_listobs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--product-row', required=True, type=int)
    parser.add_argument('--asdm', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = acquire_listobs(args.receipt, args.product_row, args.cache, args.output_dir,
                                 asdm_uid=args.asdm, source_name=args.source, offline=args.offline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Auxiliary acquisition failed: {exc}\n')
    print(f"{result['status']}: {args.output_dir}")
    return 0 if result['status'] == 'FOUND' else 3


if __name__ == '__main__':
    raise SystemExit(main())
