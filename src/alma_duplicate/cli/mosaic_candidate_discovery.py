"""Plan or run region-prefilter candidate discovery for OT Mosaic pointings."""
import argparse
import csv
import json
from pathlib import Path
from alma_duplicate.proposed_mosaic import import_proposed
from alma_duplicate.parsers.ot_pointings import MAX_BYTES
from alma_duplicate.mosaic_candidate_discovery import plan_discovery, discover_candidates


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pointings',type=Path,required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--array',choices=['7m','12m'],required=True)
    parser.add_argument('--confirm-fixed-icrs',action='store_true')
    parser.add_argument('--margin-arcsec',type=float,required=True)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        with args.pointings.open('rb') as stream:
            proposed=import_proposed(stream.read(MAX_BYTES+1),source_name=args.source,array=args.array,
                confirm_fixed_icrs=args.confirm_fixed_icrs)
        if args.live:
            report=discover_candidates(proposed,args.output_dir,margin_arcsec=args.margin_arcsec)
            print(f"{report['status']}: {report['candidate_count']} candidates; {args.output_dir}")
            return 0 if report['status']=='COMPLETED' else 3
        plan=plan_discovery(proposed,margin_arcsec=args.margin_arcsec)
        args.output_dir.mkdir(parents=True,exist_ok=False)
        (args.output_dir/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        print(f"PLANNED: {len(plan['requests'])} requests; {args.output_dir}")
        return 0
    except (OSError,ValueError,KeyError,TypeError,csv.Error) as exc:
        parser.exit(2,f'Mosaic discovery failed: {exc}\n')


if __name__=='__main__':
    raise SystemExit(main())
