"""Analyze a saved report without acquiring sources or running assessment."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from alma_duplicate.cli.profile_assessment import file_hash
from alma_duplicate.report_size import analyze_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('output already exists')
    started = perf_counter()
    with args.report.open(encoding='utf-8') as stream:
        document = json.load(stream)
    result = analyze_report(document)
    result['analysis_including_load_seconds'] = perf_counter() - started
    result['input_sha256'] = file_hash(args.report)
    result['input_bytes'] = args.report.stat().st_size
    result['input_size_matches_publication_format'] = (
        result['input_bytes'] == result['formatted_bytes'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"{result['formatted_bytes']:,} formatted bytes; {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
