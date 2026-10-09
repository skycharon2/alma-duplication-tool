"""Measure the browser backend and temporary report storage without changing science."""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter, thread_time

from alma_duplicate.cli.json_input import load_request_document
from alma_duplicate.performance import PerformanceRecorder, measure_stage
from alma_duplicate.ui.runs import BrowserAssessment, RunStore


def file_hash(path):
    if path is None:
        return None
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def profile(document, configured, *, max_bytes=1024**3):
    """One sequential run; cleanup and input hashing are outside the timed scope.

    Source stages include parsing/materialization, not solely network transit.
    Writes include JSON encoding and hashing. No extra scientific evaluation is run.
    """
    recorder = PerformanceRecorder()
    result = None
    output = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'storage_budget_bytes': max_bytes, 'execution': 'FAILED', 'files': {}}
    with_store = RunStore(max_bytes=max_bytes)
    wall, cpu = perf_counter(), thread_time()
    try:
        with recorder.record():
            result = configured.assess(document)
            if result.document is None:
                raise ValueError('No assessment report')
            run_id = with_store.add(document, result)
            with measure_stage('first_page_projection'):
                with_store.page(run_id, 1, 'matches')
            output['files'] = {p.name: p.stat().st_size
                               for p in (with_store.directory / run_id).iterdir()}
            output['execution'] = 'COMPLETED'
    except Exception as exc:
        output['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        output['wall_seconds'] = perf_counter() - wall
        output['thread_cpu_seconds'] = thread_time() - cpu
        with_store.close()
    output['stages'] = [asdict(s) for s in recorder.stages]
    output['unattributed_wall_seconds'] = max(0, output['wall_seconds'] - sum(s.wall_seconds for s in recorder.stages))
    if result is not None:
        output['assessment_status'] = str(result.status)
        if result.document is not None:
            contexts = result.document['context_evaluations']
            output['retained_contexts'] = len(contexts)
            output['sources'] = {name: source['status'] for name, source in result.document['sources'].items()}
            output['source_diagnostics'] = {}
            for name, source in result.document['sources'].items():
                metadata = source.get('source_metadata') or {}
                acquisition = (source.get('array_evidence') or {}).get('acquisition') or {}
                output['source_diagnostics'][name] = {
                    'reasons': source.get('reasons', []),
                    'upstream_status': metadata.get('status'),
                    'error_kind': metadata.get('error_kind'),
                    'missing_columns': metadata.get('missing_columns', []),
                    'aq_status': acquisition.get('status'),
                    'aq_reason': acquisition.get('reason'),
                    'aq_error': acquisition.get('error'),
                }
            output['branch_outcomes'] = dict(Counter(
                b['branch'] + ':' + b['status'] for c in contexts for b in c['branches']))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path, help='Request JSON with request and search_options')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--live-archive', action='store_true')
    source.add_argument('--archive-replay', type=Path)
    parser.add_argument('--live-aq', action='store_true')
    parser.add_argument('--queue-csv', type=Path)
    parser.add_argument('--archive-array-evidence', type=Path)
    parser.add_argument('--storage-mib', type=int, default=1024)
    parser.add_argument('--report-detail', choices=('full', 'matches'), default='matches')
    parser.add_argument('--output', type=Path, required=True, help='New timing JSON; never overwrite an existing record')
    args = parser.parse_args(argv)
    if args.storage_mib < 1:
        parser.error('--storage-mib must be positive')
    if args.output.exists():
        parser.error('output already exists')
    configured = BrowserAssessment(archive_replay=args.archive_replay, queue_csv=args.queue_csv,
                                   archive_array_evidence=args.archive_array_evidence,
                                   live_archive=args.live_archive, live_aq=args.live_aq,
                                   report_detail=args.report_detail)
    _, document = load_request_document(args.request)
    hashes = {name: file_hash(path) for name, path in {
        'request': args.request, 'queue_csv': args.queue_csv,
        'archive_replay': args.archive_replay,
        'archive_array_evidence': args.archive_array_evidence}.items() if path is not None}
    result = profile(document, configured, max_bytes=args.storage_mib * 1024**2)
    result['input_sha256'] = hashes
    result['report_detail'] = args.report_detail
    result['source_modes'] = {'archive': configured.archive_kind,
                              'live_aq': configured.live_aq, 'queue_csv': bool(configured.queue_csv)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"{result['execution']}: {result['wall_seconds']:.3f} s wall; {args.output}")
    print(f"  assessment: {result.get('assessment_status', 'unavailable')}; sources: {result.get('sources', {})}")
    for stage in result['stages']:
        print(f"  {stage['name']}: {stage['wall_seconds']:.3f} s" + (' (failed)' if stage['failed'] else ''))
    return 0 if result['execution'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
