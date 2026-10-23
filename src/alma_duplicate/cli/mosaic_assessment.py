"""Evaluate POS-MOSAIC independently for each explicitly supplied Archive candidate."""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from alma_duplicate.assessment import assess_mosaic_candidates
from alma_duplicate.mosaic_assessment_input import load_candidates
from alma_duplicate.parsers.ot_pointings import MAX_BYTES
from alma_duplicate.proposed_mosaic import import_proposed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointings',type=Path,required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--array',choices=['7m','12m'],required=True)
    parser.add_argument('--confirm-fixed-icrs',action='store_true')
    parser.add_argument('--confirm-complete',action='store_true')
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--hpbw-coefficient',type=float,required=True)
    parser.add_argument('--boundary-epsilon-arcsec',type=float,required=True)
    parser.add_argument('--assume-uniform-field-antennas',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        with args.pointings.open('rb') as stream:
            proposed=import_proposed(stream.read(MAX_BYTES+1),source_name=args.source,array=args.array,
                confirm_fixed_icrs=args.confirm_fixed_icrs,confirm_complete=args.confirm_complete)
        candidates, digest=load_candidates(args.candidates)
        report=assess_mosaic_candidates(proposed,candidates,hpbw_coefficient=args.hpbw_coefficient,
            boundary_epsilon_arcsec=args.boundary_epsilon_arcsec,
            assume_uniform_field_antennas=args.assume_uniform_field_antennas)
        report.update(proposed=proposed,candidate_manifest_sha256=digest,
            evaluation_configuration=dict(hpbw_coefficient=args.hpbw_coefficient,
                boundary_epsilon_arcsec=args.boundary_epsilon_arcsec,
                assume_uniform_field_antennas=args.assume_uniform_field_antennas))
        with args.output.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    except (OSError,ValueError,KeyError,TypeError,csv.Error,ET.ParseError) as exc:
        parser.exit(2,f'Mosaic assessment failed: {exc}\n')
    for candidate in report['candidates']:
        rule=candidate['criteria'][0]
        coverage=candidate['coverage']
        count=(f"{coverage['status_counts']['INSIDE']}/{coverage['pointing_count']} inside"
               if coverage else 'coverage unavailable')
        print(f"{candidate['context_id']}: {rule['outcome'] or rule['evaluation']}; {count}")
    print(f'REPORTED: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
