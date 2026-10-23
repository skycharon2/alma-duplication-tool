"""Group verified execution field centres into conservative diagnostic candidates."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from alma_duplicate.archive_mosaic_groups import group_pointings
from alma_duplicate.archive_mosaic_pointings import load_package_executions


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir', type=Path, required=True)
    parser.add_argument('--tolerance-arcsec', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        executions, provenance = load_package_executions(args.package_audit_dir)
        report = group_pointings(executions, tolerance_arcsec=args.tolerance_arcsec)
        report['provenance'] = dict(package_audit_dir=str(args.package_audit_dir), **provenance)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Pointing grouping failed: {exc}\n')
    print(f"GROUPED: {len(report['groups'])} components; {report['field_record_count']} field records; {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
