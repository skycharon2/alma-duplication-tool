"""Check saved Member/target inventory coverage without downloading products."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_mosaic_inventory import reconcile_inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--member', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--execution-dir', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = reconcile_inventory(args.metadata, args.execution_dir,
                                     member=args.member, source=args.source)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Inventory reconciliation failed: {exc}\n')
    print(f"{report['coverage_status']}: {args.output}")
    return 3 if report['missing_asdm_uids'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
