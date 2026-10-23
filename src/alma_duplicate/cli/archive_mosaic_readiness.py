"""Report evidence availability for Mosaic footprint inputs without computing areas."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_readiness import build_readiness


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir', type=Path, required=True)
    parser.add_argument('--array-catalog', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_readiness(args.package_audit_dir, array_catalog=args.array_catalog)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Readiness report failed: {exc}\n')
    print(f"REPORTED: {result['field_record_count']} field records; {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
