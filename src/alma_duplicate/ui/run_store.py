"""Private temporary disk storage for browser runs and indexed report pages."""

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Lock
import time
from uuid import uuid4

from alma_duplicate.performance import measure_stage
from alma_duplicate.progress import emit_progress
from alma_duplicate.reporting import report_json_chunks
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.ui.report_pages import report_page, report_projection

DEFAULT_DISK_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_AGE = 24 * 60 * 60


def _utf8_blocks(chunks):
    """Batch encoder tokens; bound each block to 64 Ki characters (256 KiB)."""
    limit = 64 * 1024
    pending, length = [], 0
    for text in chunks:
        for start in range(0, len(text), limit):
            part = text[start:start + limit]
            if length + len(part) > limit:
                yield ''.join(pending).encode('utf-8')
                pending, length = [], 0
            pending.append(part)
            length += len(part)
    if pending:
        yield ''.join(pending).encode('utf-8')


@dataclass(frozen=True)
class StoredRun:
    directory: Path
    status: str
    sha256: str
    byte_size: int
    expires_at: float
    downloads: dict


class DownloadLease:
    """Keep an already-open file valid until streaming completes or is closed."""

    def __init__(self, stream, size, release):
        self.stream, self.size, self._release = stream, size, release
        self._closed = False

    def __iter__(self):
        try:
            while chunk := self.stream.read(64 * 1024):
                yield chunk
        finally:
            self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.stream.close()
            finally:
                self._release()


class RunStore:
    """Publish complete immutable runs; retain only small descriptors in memory.

    Pages seek to indexed contexts. Downloads stream original files. Expiry is
    enforced on access; pruning deletes expired files on subsequent requests.
    In-flight downloads keep a lease, so eviction never truncates their files.
    This is one local process, not an authenticated persistent report service.
    """

    def __init__(self, max_runs=20, max_bytes=DEFAULT_DISK_BYTES, *,
                 max_age=DEFAULT_MAX_AGE, directory=None, clock=time.monotonic):
        if any(type(v) is not int or v < 1 for v in (max_runs, max_bytes, max_age)):
            raise ValueError('Run retention limits must be positive integers')
        self._max_runs, self._max_bytes, self.max_age = max_runs, max_bytes, max_age
        self._clock = clock
        self._temporary = TemporaryDirectory(prefix='alma-ui-runs-', dir=directory)
        self.directory = Path(self._temporary.name)
        self._runs, self._retired, self._leases = OrderedDict(), {}, {}
        self._size, self._closed = 0, False
        self._lock = Lock()
        self._write_lock = Lock()

    def _remove(self, item):
        shutil.rmtree(item.directory)
        self._size -= item.byte_size

    def _retire(self, run_id):
        item = self._runs.pop(run_id)
        if self._leases.get(run_id):
            self._retired[run_id] = item
        else:
            self._remove(item)

    def _prune_locked(self):
        now = self._clock()
        for run_id, item in list(self._runs.items()):
            if now >= item.expires_at:
                self._retire(run_id)

    def prune(self):
        with self._lock:
            if not self._closed:
                self._prune_locked()

    def close(self):
        with self._write_lock, self._lock:
            if self._closed:
                return
            self._closed = True
            for run_id in list(self._runs):
                self._retire(run_id)
            if not self._leases:
                self._temporary.cleanup()

    def add(self, request_document, result):
        # One staging run at a time bounds temporary space, and close waits for
        # publication/rollback before removing the private root directory.
        emit_progress("storage_wait")
        with self._write_lock:
            with self._lock:
                if self._closed:
                    raise ValueError('Run store is closed')
            return self._add(request_document, result)

    def _add(self, request_document, result):
        if result.document is None:
            raise ValueError('An assessment without a report cannot be retained')
        document = result.document
        emit_progress('inspection')
        with measure_stage("inspection"):
            inspection = inspect_report(document, inspection_version='3')
        for context in document['context_evaluations']:
            for field in ('reference', 'criteria', 'branches', 'line_pairs'):
                if field not in context:
                    raise ValueError(f'Missing context field: {field}')
        run_id = uuid4().hex
        staging = self.directory / ('.pending-' + run_id)
        staging.mkdir(mode=0o700)
        size = 0
        emit_progress('storage', 0, unit='bytes')

        def write(name, chunks):
            nonlocal size
            digest, length = hashlib.sha256(), 0
            with (staging / name).open('xb') as stream:
                os.chmod(stream.name, 0o600)
                for raw in _utf8_blocks(chunks):
                    size += len(raw)
                    if size > self._max_bytes:
                        raise ValueError("Report exceeds this application's disk retention limit")
                    stream.write(raw)
                    emit_progress("storage", size, unit="bytes")
                    digest.update(raw)
                    length += len(raw)
            return length, digest.hexdigest()

        try:
            downloads = {}
            for kind, data in [('report', document), ('inspection', inspection), ('request', request_document)]:
                with measure_stage('write_' + kind):
                    downloads[kind] = write(kind + '.json', report_json_chunks(data))
            offsets = []

            def context_lines():
                position = 0
                for context in document['context_evaluations']:
                    line = json.dumps(context, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n'
                    length = len(line.encode('utf-8'))
                    offsets.append((position, length))
                    position += length
                    yield line

            with measure_stage('write_context_index'):
                write('contexts.jsonl', context_lines())
            with measure_stage("view_projection"):
                projection = report_projection(document, inspection, compact=True)
            projection['offsets'] = offsets
            with measure_stage('write_view'):
                write('view.json', report_json_chunks(projection))
            with self._lock:
                if self._closed:
                    raise ValueError('Run store is closed')
                self._prune_locked()
                # Plan eviction before modifying any still-valid run. Leased files
                # still consume disk and cannot be counted as immediately freed.
                victims, projected_size, remaining = [], self._size + size, len(self._runs) + 1
                for old_id, old in self._runs.items():
                    if remaining <= self._max_runs and projected_size <= self._max_bytes:
                        break
                    victims.append(old_id)
                    remaining -= 1
                    if not self._leases.get(old_id):
                        projected_size -= old.byte_size
                if projected_size > self._max_bytes:
                    raise ValueError('Disk retention budget is occupied by active downloads')
                target = self.directory / run_id
                staging.rename(target)
                item = StoredRun(target, str(result.status), downloads['report'][1], size,
                                 self._clock() + self.max_age, downloads)
                for old_id in victims:
                    self._retire(old_id)
                self._runs[run_id] = item
                self._size += size
            return run_id
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def page(self, run_id, page=1, view='matches'):
        with self._lock:
            self._prune_locked()
            item = self._runs.get(run_id)
            if item is None:
                return None
            projection = json.loads((item.directory / 'view.json').read_bytes())
            with (item.directory / 'contexts.jsonl').open('rb') as stream:
                def context(index):
                    offset, length = projection['offsets'][index]
                    stream.seek(offset)
                    return json.loads(stream.read(length))
                data = report_page(projection, page, view, context)
            data.update(item=item, run=item, disk_backed=True, retention_hours=self.max_age / 3600)
            return data

    def open_download(self, run_id, kind):
        if kind not in {'report', 'inspection', 'request'}:
            raise ValueError('Unknown download kind')
        with self._lock:
            self._prune_locked()
            item = self._runs.get(run_id)
            if item is None:
                return None
            stream = (item.directory / (kind + '.json')).open('rb')
            self._leases[run_id] = self._leases.get(run_id, 0) + 1

        def release():
            with self._lock:
                self._leases[run_id] -= 1
                if not self._leases[run_id]:
                    del self._leases[run_id]
                    if run_id in self._retired:
                        self._remove(self._retired.pop(run_id))
                if self._closed and not self._leases:
                    self._temporary.cleanup()

        return DownloadLease(stream, item.downloads[kind][0], release)
