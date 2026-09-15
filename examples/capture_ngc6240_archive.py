"""Explicit live capture for the fixed dual-source request; outputs to a new folder."""
import argparse
from datetime import datetime, UTC
import hashlib
import io
import json
from pathlib import Path

import requests
from astropy.io.votable import parse
from pyvo.dal import TAPResults

from alma_duplicate.cli.evaluate import main as evaluate
from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://almascience.eso.org/tap'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New directory; existing evidence is never overwritten')
    args = parser.parse_args()
    folder = args.output_dir
    folder.mkdir(parents=True, exist_ok=False)
    entries = []

    class CaptureService:
        def run_sync(self, query, *, maxrec):
            started = datetime.now(UTC).isoformat()
            response = requests.get(ENDPOINT + '/sync', params={
                'REQUEST': 'doQuery', 'LANG': 'ADQL', 'FORMAT': 'votable',
                'MAXREC': maxrec, 'QUERY': query,
            }, timeout=90)
            response.raise_for_status()
            name = f'response-{len(entries)}.xml'
            (folder/name).write_bytes(response.content)
            entries.append({
                'adql': query, 'maxrec': maxrec, 'file': name,
                'sha256': hashlib.sha256(response.content).hexdigest(),
                'started_at': started, 'finished_at': datetime.now(UTC).isoformat(),
            })
            return TAPResults(parse(io.BytesIO(response.content)))

    class CaptureClient(ArchiveClient):
        def search(self, spec):
            result = super().search(spec)
            p = result.provenance
            manifest = {
                'replay_version': '1', 'endpoint': p.endpoint, 'maxrec': self.maxrec,
                'query_run_id': p.query_run_id, 'started_at': p.started_at.isoformat(),
                'finished_at': p.finished_at.isoformat(), 'responses': entries,
                'expected_count': p.expected_count, 'retrieved_count': p.retrieved_count,
                'status': result.status.value,
            }
            (folder/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
            return result

    return evaluate([
        '--request', str(ROOT/'examples/dual_source/request.json'),
        '--queue-csv', str(ROOT/'tests/fixtures/queue/queue_pipeline_v1.csv'),
        '--live-archive', '--queue-candidate-beam', '--output', str(folder/'live-report.json'),
    ], archive_client_factory=lambda: CaptureClient(
        ENDPOINT, executor=PyvoTapExecutor(ENDPOINT, service=CaptureService())))


if __name__ == '__main__':
    raise SystemExit(main())
