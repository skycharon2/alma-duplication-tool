"""Profile the actual batch path; never change scientific reports or retention policy."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import resource
from threading import Lock
from time import perf_counter, process_time

from alma_duplicate.cli.profile_assessment import file_hash
from alma_duplicate.ui.batch_assessment import execute_batch
from alma_duplicate.ui.runs import BrowserAssessment, RunStore


def profile_batch(values, rows, raw, configured, *, workers=1, max_bytes=1024**3,
                  format='csv'):
    records = []
    lock = Lock()
    def collect(record):
        with lock:
            records.append(record)
    output = dict(schema_version='batch_performance_1',
                  started_at=datetime.now(timezone.utc).isoformat(),
                  python=platform.python_version(), platform=platform.platform(),
                  workers=workers, storage_budget_bytes=max_bytes, execution='FAILED')
    runs = RunStore(max_bytes=max_bytes)
    wall, cpu = perf_counter(), process_time()
    try:
        batch_id = execute_batch(values, rows, raw, runner=configured, runs=runs,
            owner='performance', submission_token='0' * 32, format=format,
            max_workers=workers, performance=collect)
        manifest = runs.batches.get(batch_id, 'performance')
        if manifest is None:
            raise RuntimeError('Batch manifest unavailable')
        by_key = {(r['source_id'], r['purpose']): r for r in records}
        ordered = []
        for source in manifest['sources']:
            for report in source['reports']:
                record = by_key.get((source['source_id'], report['purpose']),
                    dict(source_id=source['source_id'], purpose=report['purpose'], stages=[]))
                record.update(state=report['state'], availability=report['availability'], files={})
                if report['availability'] == 'AVAILABLE':
                    record['files'] = {p.name: p.stat().st_size for p in
                        (runs.directory / report['run_id']).iterdir() if p.is_file()}
                record['retained_bytes'] = sum(record['files'].values())
                ordered.append(record)
        output['branches'] = ordered
        output['execution'] = ('COMPLETED' if manifest['execution_complete'] and
            all(r['state'] == 'COMPLETED' and r['availability'] == 'AVAILABLE' for r in ordered)
            else 'INCOMPLETE')
    except Exception as exc:
        output.update(error_type=type(exc).__name__, error=str(exc), branches=records)
    finally:
        output['wall_seconds'] = perf_counter() - wall
        output['process_cpu_seconds'] = process_time() - cpu
        # OS process-lifetime high-water mark; not a per-target allocation measurement.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        output['process_lifetime_peak_rss_bytes'] = int(peak if platform.system() == 'Darwin' else peak * 1024)
        runs.close()
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('setup', type=Path, help='JSON containing browser form values and rows')
    parser.add_argument('targets', type=Path)
    parser.add_argument('--format', choices=['csv', 'txt'], default='csv')
    parser.add_argument('--workers', type=int, choices=[1, 2, 3, 4], default=1)
    parser.add_argument('--sources', choices=['queue', 'archive', 'both'], required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--archive-replay', type=Path)
    group.add_argument('--live-archive', action='store_true')
    parser.add_argument('--live-aq', action='store_true')
    parser.add_argument('--archive-array-evidence', type=Path)
    parser.add_argument('--queue-csv', type=Path)
    parser.add_argument('--storage-mib', type=int, default=1024)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.storage_mib < 1 or args.output.exists():
        parser.error('storage budget must be positive and output must not exist')
    if args.sources in ('queue', 'both') and args.queue_csv is None:
        parser.error('Queue profiling requires an explicit --queue-csv snapshot')
    if args.sources in ('archive', 'both') and not (args.archive_replay or args.live_archive):
        parser.error('Archive profiling requires replay or explicit live access')
    setup = json.loads(args.setup.read_text())
    values = dict(setup['values'], sources={'queue': ['QUEUE'], 'archive': ['ARCHIVE'],
                                         'both': ['ARCHIVE', 'QUEUE']}[args.sources])
    paths = dict(setup=args.setup, targets=args.targets, queue_csv=args.queue_csv,
                 archive_replay=args.archive_replay, archive_array_evidence=args.archive_array_evidence)
    hashes = {k: file_hash(v) for k, v in paths.items() if v is not None}
    runner = BrowserAssessment(queue_csv=args.queue_csv, archive_replay=args.archive_replay,
        archive_array_evidence=args.archive_array_evidence, live_archive=args.live_archive,
        live_aq=args.live_aq, report_detail='matches')
    output = profile_batch(values, setup['rows'], args.targets.read_bytes(), runner,
                           workers=args.workers, max_bytes=args.storage_mib * 1024**2, format=args.format)
    output.update(input_sha256=hashes, selected_sources=args.sources,
                  archive_mode=runner.archive_kind, live_aq=args.live_aq)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"{output['execution']}: {output['wall_seconds']:.3f}s; {args.output}")
    for branch in output.get('branches', []):
        print(f"  {branch['source_id']} {branch['purpose']}: {branch.get('state', 'UNKNOWN')}; "
              f"availability={branch.get('availability', 'UNKNOWN')}; sources={branch.get('sources', {})}")
    return 0 if output['execution'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
