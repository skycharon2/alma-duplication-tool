"""Validate explicit per-SPW footprint diagnostics and optional s_region vertices."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.archive_mosaic_footprint_validation import validate_footprints
from alma_duplicate.archive_mosaic_pipeline import MAX_METADATA_BYTES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir', type=Path, required=True)
    parser.add_argument('--array-catalog', type=Path, required=True)
    parser.add_argument('--asdm', required=True)
    parser.add_argument('--spw', type=int, action='append', required=True)
    parser.add_argument('--hpbw-coefficient', type=float, required=True)
    parser.add_argument('--frequency-choice', choices=['reported-spw-centre'], required=True)
    parser.add_argument('--assume-uniform-field-antennas', action='store_true')
    parser.add_argument('--boundary-epsilon-arcsec', type=float, required=True)
    parser.add_argument('--boundary-offset-arcsec', type=float, required=True)
    parser.add_argument('--region-metadata', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        region_raw = None
        if args.region_metadata:
            with args.region_metadata.open('rb') as stream:
                region_raw = stream.read(MAX_METADATA_BYTES + 1)
        result = validate_footprints(build_readiness(args.package_audit_dir, array_catalog=args.array_catalog),
            asdm_uid=args.asdm, spw_ids=args.spw, hpbw_coefficient=args.hpbw_coefficient,
            frequency_choice=args.frequency_choice, assume_uniform_field_antennas=args.assume_uniform_field_antennas,
            boundary_epsilon_arcsec=args.boundary_epsilon_arcsec, boundary_offset_arcsec=args.boundary_offset_arcsec,
            region_raw=region_raw)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Footprint validation failed: {exc}\n')
    print(f"{result['status']}: {args.output}")
    return 0 if result['status'] == 'DIAGNOSTIC_CHECKS_PASSED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
