"""Compare bounded AQ terms queries against production per-Member retrieval."""
import argparse
from collections import Counter
from pathlib import Path
from time import perf_counter

from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
from alma_duplicate.performance import PerformanceRecorder


def science_rows(result):
    return Counter((r.observation_id, r.member_ous_uid, r.source_name, r.raw_label)
                   for r in result.catalog.records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('members', type=Path, help='Public Member OUS UIDs, one per line')
    args = parser.parse_args()
    members = tuple(dict.fromkeys(args.members.read_text().split()))
    if len(members) < 32:
        parser.error('provide at least 32 distinct Member UIDs')
    baseline = None
    for label, client in [('individual', ArchiveAqClient(member_workers=2)),
                          ('groups of 16', ArchiveAqClient(member_workers=2, group_size=16)),
                          ('groups of 32', ArchiveAqClient(member_workers=2, group_size=32))]:
        start = perf_counter()
        with PerformanceRecorder().record() as recorder:
            result = client.fetch_members(members)
        elapsed = perf_counter() - start
        counts = tuple((q.member_ous_uid, q.total_hits) for q in result.queries)
        current = counts, science_rows(result)
        if baseline is None:
            baseline = current
        print(label, round(elapsed, 3), 'seconds;', sum(current[1].values()), 'rows;',
              'groups', dict(Counter(s.name for s in recorder.stages if s.name.startswith('aq_group'))), 'exact parity', current == baseline, flush=True)
        if current != baseline:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
