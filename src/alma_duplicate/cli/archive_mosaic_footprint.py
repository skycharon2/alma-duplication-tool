"""Build an explicit single-execution/SPW half-power footprint diagnostic."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.archive_mosaic_footprint import circular_footprint, probe_footprint


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-audit-dir', type=Path, required=True)
    parser.add_argument('--array-catalog', type=Path, required=True)
    parser.add_argument('--asdm', required=True)
    parser.add_argument('--spw', type=int, required=True)
    parser.add_argument('--hpbw-coefficient', type=float, required=True)
    parser.add_argument('--frequency-choice', choices=['reported-spw-centre'], required=True)
    parser.add_argument('--assume-uniform-field-antennas', action='store_true')
    parser.add_argument('--probes', type=Path)
    parser.add_argument('--boundary-epsilon-arcsec', type=float)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if (args.probes is None) != (args.boundary_epsilon_arcsec is None):
        parser.error('Supply probes and boundary epsilon together')
    try:
        readiness = build_readiness(args.package_audit_dir, array_catalog=args.array_catalog)
        report = circular_footprint(readiness, asdm_uid=args.asdm, spw_id=args.spw,
            hpbw_coefficient=args.hpbw_coefficient, frequency_choice=args.frequency_choice,
            assume_uniform_field_antennas=args.assume_uniform_field_antennas)
        if args.probes is not None:
            report['probe_results'] = probe_footprint(report, json.loads(args.probes.read_bytes()),
                                                    boundary_epsilon_arcsec=args.boundary_epsilon_arcsec)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        parser.exit(2, f'Footprint diagnostic failed: {exc}\n')
    print(f"DIAGNOSTIC: {len(report['circles'])} circles; radius {report['half_power_radius_arcsec']:.6f} arcsec; {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
