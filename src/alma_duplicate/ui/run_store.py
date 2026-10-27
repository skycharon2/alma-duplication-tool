"""Private temporary disk storage for browser runs and indexed report pages."""

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
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
MAX_REMOVAL_NOTICES = 1024


def _indexed_report_blocks(document, offsets):
    """Write the publication JSON once, recording UTF-8 context byte ranges.

    Only the root object and its context array are framed here. The standard
    encoder handles every value, including escaped strings and nested objects.
    Indentation matches report_json_chunks exactly; offsets exclude separators.
    """
    encoder = json.JSONEncoder(indent=2, ensure_ascii=False, allow_nan=False)
    position = 0

    def emit(chunks):
        nonlocal position
        for block in _utf8_blocks(chunks):
            position += len(block)
            yield block

    def emit_value(value, indent):
        nonlocal position
        # Reindent batched bytes rather than visiting every encoder token twice.
        # JSON strings contain escaped newlines, so literal LF is formatting only.
        for block in _utf8_blocks(encoder.iterencode(value)):
            block = block.replace(b'\n', b'\n' + indent)
            position += len(block)
            yield block

    yield from emit(['{'])
    for index, (key, value) in enumerate(document.items()):
        yield from emit([',\n' if index else '\n', '  ', encoder.encode(key), ': '])
        if (key == 'context_evaluations' or (key == 'candidates' and
                document.get('schema_version') == 'archive_mosaic_backend_2')) and value:
            yield from emit(['[\n    '])
            for context_index, context in enumerate(value):
                if context_index:
                    yield from emit([',\n    '])
                start = position
                yield from emit_value(context, b'    ')
                offsets.append((start, position - start))
            yield from emit(['\n  ]'])
        else:
            yield from emit_value(value, b'  ')
    yield from emit(['\n}\n' if document else '}\n'])


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
        self._session_id = uuid4().hex
        self._removal_notices = OrderedDict()
        self._size, self._closed = 0, False
        self._lock = Lock()
        self._write_lock = Lock()

    def _remove(self, item):
        shutil.rmtree(item.directory)
        self._size -= item.byte_size

    def _retire(self, run_id, reason):
        item = self._runs.pop(run_id)
        self._removal_notices[run_id] = reason
        while len(self._removal_notices) > MAX_REMOVAL_NOTICES:
            self._removal_notices.popitem(last=False)
        if self._leases.get(run_id):
            self._retired[run_id] = item
        else:
            self._remove(item)

    def _prune_locked(self):
        now = self._clock()
        for run_id, item in list(self._runs.items()):
            if now >= item.expires_at:
                self._retire(run_id, 'EXPIRED')

    def unavailable_reason(self, run_id):
        """Explain known removals without guessing why an unknown ID is absent."""
        with self._lock:
            self._prune_locked()
            if run_id in self._runs:
                return None
            if run_id in self._removal_notices:
                return self._removal_notices[run_id]
            if (re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{32}', run_id)
                    and run_id.split('.')[0] != self._session_id):
                return 'OTHER_SESSION'
            return 'UNKNOWN'

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
                self._retire(run_id, 'CLOSED')
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
            mosaic = document.get("schema_version") == "archive_mosaic_backend_2"
            inspection = ({"schema_version": "mosaic_browser_inspection_1",
                           "assessment_status": document["assessment_status"],
                           "absence_interpretation": document["absence_interpretation"]}
                          if mosaic else inspect_report(document, inspection_version='3'))
        for context in document.get('context_evaluations', []):
            for field in ('reference', 'criteria', 'branches', 'line_pairs'):
                if field not in context:
                    raise ValueError(f'Missing context field: {field}')
        run_id = self._session_id + '.' + uuid4().hex
        staging = self.directory / ('.pending-' + run_id)
        staging.mkdir(mode=0o700)
        size = 0
        emit_progress('storage', 0, unit='bytes')

        def write(name, blocks):
            nonlocal size
            digest, length = hashlib.sha256(), 0
            with (staging / name).open('xb') as stream:
                os.chmod(stream.name, 0o600)
                for raw in blocks:
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
            offsets = []
            with measure_stage('write_report'):
                downloads['report'] = write('report.json', _indexed_report_blocks(document, offsets))
            for kind, data in [('inspection', inspection), ('request', request_document)]:
                with measure_stage('write_' + kind):
                    downloads[kind] = write(kind + '.json', _utf8_blocks(report_json_chunks(data)))
            with measure_stage("view_projection"):
                projection = ({"mosaic": True, "summary": {"target": document["proposed"]["source_name"]},
                               "document": {"proposed": {k: document["proposed"][k] for k in ("source_name", "row_count")},
                                            "assessment_status": document["assessment_status"],
                                            "discovery": {"status": document["discovery"]["status"]}},
                               "candidate_count": len(document["candidates"])}
                              if mosaic else report_projection(document, inspection, compact=True))
            projection['offsets'] = offsets
            with measure_stage('write_view'):
                write('view.json', _utf8_blocks(report_json_chunks(projection)))
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
                    self._retire(old_id, 'EVICTED')
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
            if projection.get("mosaic"):
                pages = max(1, math.ceil(projection["candidate_count"] / 20))
                if page < 1 or page > pages:
                    raise IndexError("Page out of range")
                with (item.directory / 'report.json').open('rb') as stream:
                    candidates = []
                    for offset, length in projection['offsets'][(page-1)*20:page*20]:
                        stream.seek(offset)
                        candidates.append(json.loads(stream.read(length)))
                return dict(mosaic=True, document=projection["document"], candidates=candidates,
                            candidate_count=projection["candidate_count"],
                            page=page, pages=pages, run=item, retention_hours=self.max_age / 3600)
            with (item.directory / 'report.json').open('rb') as stream:
                def context(index):
                    offset, length = projection['offsets'][index]
                    stream.seek(offset)
                    return json.loads(stream.read(length))
                data = report_page(projection, page, view, context)
            data.update(item=item, run=item, disk_backed=True, retention_hours=self.max_age / 3600,
                        remaining_minutes=max(0, math.ceil((item.expires_at - self._clock()) / 60)))
            return data

    def summaries(self, run_ids):
        """List only explicitly supplied browser links, without loading contexts."""
        with self._lock:
            self._prune_locked()
            result = []
            for run_id in dict.fromkeys(run_ids):
                item = self._runs.get(run_id)
                if item is None:
                    continue
                projection = json.loads((item.directory / 'view.json').read_bytes())
                result.append({'id': run_id, 'target': projection['summary']['target'],
                               'generated_at': projection['document'].get('generated_at'),
                               'status': item.status})
            return result

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
