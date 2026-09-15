"""Replay one captured TAP query sequence through the production Archive client.

Original VOTables retain rows, masks, field descriptors and QUERY_STATUS. Exact
ADQL/maxrec matching prevents using a different cone or filtering by expected UID.
"""
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path

from astropy.io.votable import parse
from pyvo.dal import TAPResults

from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor


class RecordedArchiveClient:
    """A single-use offline query replay, not a general Archive cache."""

    def __init__(self, manifest_path):
        try:
            self._load(Path(manifest_path))
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("Malformed Archive replay manifest") from exc

    def _load(self, path):
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise ValueError('Archive replay manifest must be an object')
        if manifest['replay_version'] != '1':
            raise ValueError('Unsupported Archive replay version')
        self._manifest = manifest
        self.input_paths = [path.resolve()]
        self._responses = []
        self._index = 0
        for entry in manifest['responses']:
            name = entry['file']
            if Path(name).name != name:
                raise ValueError('Replay response must be a sibling file')
            self.input_paths.append((path.parent / name).resolve())
            data = (path.parent / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError(f'Archive replay checksum mismatch: {name}')
            self._responses.append((entry, data))
        self.metadata = {
            'mode': 'OFFLINE_REPLAY', 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'capture_started_at': manifest['started_at'],
            'capture_finished_at': manifest['finished_at'],
            'response_sha256': [entry['sha256'] for entry, _ in self._responses],
        }

    def run_sync(self, query, *, maxrec):
        if self._index >= len(self._responses):
            raise ValueError('Archive replay exhausted')
        entry, data = self._responses[self._index]
        if query != entry['adql'] or maxrec != entry['maxrec']:
            raise ValueError('Archive replay query/maxrec mismatch')
        self._index += 1
        return TAPResults(parse(io.BytesIO(data)))

    def search(self, spec):
        m = self._manifest
        times = iter((datetime.fromisoformat(m['started_at']), datetime.fromisoformat(m['finished_at'])))
        client = ArchiveClient(
            m['endpoint'], maxrec=m['maxrec'],
            executor=PyvoTapExecutor(m['endpoint'], service=self),
            clock=lambda: next(times), run_id_factory=lambda: m['query_run_id'],
        )
        result = client.search(spec)
        if self._index != len(self._responses):
            raise ValueError('Archive replay did not consume the full capture')
        if (result.status.value != m['status'] or
                result.provenance.expected_count != m['expected_count'] or
                result.provenance.retrieved_count != m['retrieved_count']):
            raise ValueError('Archive replay completeness differs from capture')
        return result
