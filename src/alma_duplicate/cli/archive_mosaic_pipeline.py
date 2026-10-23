"""Acquire and reconstruct one Archive Mosaic execution from saved metadata."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_mosaic_pipeline import run_archive_mosaic_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--product-row', type=int, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = run_archive_mosaic_pipeline(metadata=args.metadata, receipt=args.receipt,
                                             row_index=args.product_row, cache=args.cache,
                                             output=args.output_dir, offline=args.offline)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Mosaic pipeline failed: {exc}\n')
    print(f"{result['status']}: {args.output_dir}")
    return 0 if result['status'] == 'RECONSTRUCTED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
