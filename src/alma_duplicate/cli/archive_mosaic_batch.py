"""Reconstruct and summarize executions in a captured Member/target inventory."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_mosaic_batch import run_batch


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('metadata', 'capture-receipt', 'cache', 'output-dir'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--member', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--datalink-response', type=Path)
    parser.add_argument('--reuse-dir', type=Path, action='append', default=[])
    parser.add_argument('--package-audit-dir', type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = run_batch(metadata=args.metadata, capture_receipt=args.capture_receipt,
            member=args.member, source=args.source, cache=args.cache, output=args.output_dir,
            datalink_response=args.datalink_response, reuse_dirs=args.reuse_dir, offline=args.offline, package_audit_dir=args.package_audit_dir)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Mosaic batch failed: {exc}\n')
    print(f"{report['status']}: {args.output_dir}")
    return 0 if report['status'] in ('VISIBLE_INVENTORY_COVERED', 'PACKAGE_EVIDENCE_COVERED') else 3


if __name__ == '__main__':
    raise SystemExit(main())
