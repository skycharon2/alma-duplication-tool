"""Prepare Archive pointings automatically from a Mosaic discovery report."""
from alma_duplicate.mosaic_resource_limits import add_resource_arguments, resource_arguments
import argparse
import json
from pathlib import Path
from alma_duplicate.mosaic_candidate_preparation import prepare_candidates


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery',type=Path,required=True)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-candidates', type=int, default=100)
    add_resource_arguments(parser)
    args=parser.parse_args(argv)
    try:
        with args.discovery.open('rb') as stream:raw=stream.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError('Discovery report exceeds 5 MB')
        report=prepare_candidates(json.loads(raw),output=args.output_dir,cache=args.cache,
                                  resource_limits=resource_arguments(args),
                                  resume=args.resume, max_candidates=args.max_candidates)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(2,f'Candidate preparation failed: {exc}\n')
    for c in report['candidates']:
        print(f"{c['source_name']} {c['member_ous_uid']}: {c['status']}")
    print(f"{report['status']}: {args.output_dir}")
    return 0 if report['status']=='COMPLETED' else 3


if __name__=='__main__':
    raise SystemExit(main())
