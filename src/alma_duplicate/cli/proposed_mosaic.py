"""Import OT native absolute pointings, optionally assess selected Archive coverage."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.parsers.ot_pointings import MAX_BYTES
from alma_duplicate.proposed_mosaic import import_proposed, assess_proposed
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.mosaic_coverage_union import assess_union


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
    parser.add_argument('--selections', type=Path, help='JSON list of explicit asdm_uid/spw_id pairs')
    parser.add_argument('--asdm')
    parser.add_argument('--spw', type=int)
    parser.add_argument('--hpbw-coefficient', type=float)
    parser.add_argument('--boundary-epsilon-arcsec', type=float)
    parser.add_argument('--assume-uniform-field-antennas', action='store_true')
    args = parser.parse_args(argv)
    common = [args.package_audit_dir, args.array_catalog,
              args.hpbw_coefficient, args.boundary_epsilon_arcsec]
    assess = any(v is not None for v in common + [args.asdm, args.spw, args.selections])
    if args.selections is not None and (args.asdm is not None or args.spw is not None):
        parser.error('Use selections or a single ASDM/SPW, not both')
    if assess and (any(v is None for v in common) or
                   (args.selections is None and (args.asdm is None or args.spw is None))):
        parser.error('Coverage requires audit, catalog, coefficient, epsilon and explicit selection')
    try:
        with args.pointings.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        report = import_proposed(raw, source_name=args.source, array=args.array,
            confirm_fixed_icrs=args.confirm_fixed_icrs, confirm_complete=args.confirm_complete)
        if assess:
            readiness = build_readiness(args.package_audit_dir, array_catalog=args.array_catalog)
            kwargs = dict(hpbw_coefficient=args.hpbw_coefficient,
                boundary_epsilon_arcsec=args.boundary_epsilon_arcsec,
                assume_uniform_field_antennas=args.assume_uniform_field_antennas)
            if args.selections is not None:
                with args.selections.open('rb') as stream:
                    selection_raw = stream.read(65537)
                if len(selection_raw) > 65536:
                    raise ValueError('Selection file exceeds 64 KB')
                report = assess_union(report, readiness,
                    selections=json.loads(selection_raw), **kwargs)
            else:
                report = assess_proposed(report, readiness, asdm_uid=args.asdm, spw_id=args.spw, **kwargs)
        if assess:
            from alma_duplicate.assessment import assess_mosaic_candidates
            selected = (json.loads(selection_raw) if args.selections is not None else
                        [dict(asdm_uid=args.asdm, spw_id=args.spw)])
            formal = assess_mosaic_candidates(report['proposed'], [dict(
                context_id='ARCHIVE:' + readiness['member_ous_uid'] + ':' + readiness['source_name'],
                member_ous_uid=readiness['member_ous_uid'], source_name=readiness['source_name'],
                readiness=readiness, selections=selected)], **kwargs)
            report['position_criterion'] = formal['candidates'][0]['criteria'][0]
            report['duplication_status'] = 'NOT_EVALUATED'
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError, csv.Error, ET.ParseError) as exc:
        parser.exit(2, f'Proposed Mosaic failed: {exc}\n')
    print(f"{report.get('spatial_condition', 'IMPORTED')}: {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
