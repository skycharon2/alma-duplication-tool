"""Import OT native absolute pointings, optionally assess selected Archive coverage."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.parsers.ot_pointings import MAX_BYTES
from alma_duplicate.proposed_mosaic import import_proposed, assess_proposed
from alma_duplicate.archive_mosaic_readiness import build_readiness


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointings', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--array', choices=['7m', '12m'], required=True)
    parser.add_argument('--confirm-fixed-icrs', action='store_true')
    parser.add_argument('--confirm-complete', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--package-audit-dir', type=Path)
    parser.add_argument('--array-catalog', type=Path)
    parser.add_argument('--asdm')
    parser.add_argument('--spw', type=int)
    parser.add_argument('--hpbw-coefficient', type=float)
    parser.add_argument('--boundary-epsilon-arcsec', type=float)
    parser.add_argument('--assume-uniform-field-antennas', action='store_true')
    args = parser.parse_args(argv)
    selection = [args.package_audit_dir, args.array_catalog, args.asdm, args.spw,
                 args.hpbw_coefficient, args.boundary_epsilon_arcsec]
    assess = any(v is not None for v in selection)
    if assess and any(v is None for v in selection):
        parser.error('Coverage requires package audit, array catalog, ASDM, SPW, coefficient and epsilon')
    try:
        with args.pointings.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        report = import_proposed(raw, source_name=args.source, array=args.array,
            confirm_fixed_icrs=args.confirm_fixed_icrs, confirm_complete=args.confirm_complete)
        if assess:
            readiness = build_readiness(args.package_audit_dir, array_catalog=args.array_catalog)
            report = assess_proposed(report, readiness, asdm_uid=args.asdm, spw_id=args.spw,
                hpbw_coefficient=args.hpbw_coefficient, boundary_epsilon_arcsec=args.boundary_epsilon_arcsec,
                assume_uniform_field_antennas=args.assume_uniform_field_antennas)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, csv.Error, ET.ParseError) as exc:
        parser.exit(2, f'Proposed Mosaic failed: {exc}\n')
    print(f"{report.get('spatial_condition', 'IMPORTED')}: {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
