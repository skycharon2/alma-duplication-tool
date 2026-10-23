"""Audit all supported original MS listobs in a Member auxiliary package."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_package_audit import audit_package


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('metadata', 'capture-receipt', 'receipt', 'cache', 'output-dir'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--product-row', type=int, required=True)
    parser.add_argument('--member', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = audit_package(metadata=args.metadata, capture_receipt=args.capture_receipt,
            receipt=args.receipt, row_index=args.product_row, cache=args.cache, output=args.output_dir,
            member=args.member, source=args.source, offline=args.offline)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Package audit failed: {exc}\n')
    print(f"{report['status']}: {len(report['executions'])} executions; {args.output_dir}")
    return 3 if report['status'] == 'UNRESOLVED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
