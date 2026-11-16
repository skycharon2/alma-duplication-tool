"""Bounded process-local batch manifests and owner-scoped report references."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from threading import RLock
from uuid import uuid4

TERMINAL = {'COMPLETED', 'FAILED'}


class BatchStore:
    """Keep small JSON manifests; RunStore alone owns report artifacts.

    Mutations publish only after serialization and budget checks. Active batches
    are not capacity-evicted. Expiry is fixed at creation, never extended by reads.
    Owners are opaque browser scope tokens, not an authentication system.
    """

    def __init__(self, runs, *, max_batches=20, max_bytes=1_000_000, clock):
        if any(type(v) is not int or v < 1 for v in (max_batches, max_bytes)):
            raise ValueError('Batch retention limits must be positive integers')
        self._runs, self._clock = runs, clock
        self._max_batches, self._max_bytes = max_batches, max_bytes
        self._records, self._reverse, self._submissions = OrderedDict(), {}, {}
        self._lock, self._closed = RLock(), False

    def _remove(self, batch_id):
        item = self._records.pop(batch_id)
        if item.get('submission_token') is not None:
            self._submissions.pop((item['owner'], item['submission_token']), None)
        for source in item['manifest']['sources']:
            for report in source['reports']:
                if report['run_id']:
                    self._reverse.pop(report['run_id'], None)

    def prune(self):
        with self._lock:
            for batch_id, item in list(self._records.items()):
                if self._clock() >= item['expires_at']:
                    self._remove(batch_id)

    def close(self):
        with self._lock:
            self._closed = True
            self._records.clear()
            self._reverse.clear()
            self._submissions.clear()

    @staticmethod
    def _size(manifest):
        return len(json.dumps(manifest, ensure_ascii=False, allow_nan=False).encode('utf-8'))

    @staticmethod
    def _finished(manifest):
        return all(r['state'] in TERMINAL for s in manifest['sources'] for r in s['reports'])

    def create(self, owner, shared_setup, sources, input_sha256, purposes, *,
               submission_token=None, reserve_execution=False):
        """Reserve an ordered batch; sources are parsed source-list records."""
        if not isinstance(owner, str) or not owner or len(owner) > 256:
            raise ValueError('A bounded browser owner token is required')
        if submission_token is not None and (not isinstance(submission_token, str) or
                re.fullmatch('[a-f0-9]{32}', submission_token) is None):
            raise ValueError('Expected a 32-character hexadecimal submission token')
        if not isinstance(shared_setup, dict):
            raise ValueError('Expected shared setup mapping')
        if not isinstance(input_sha256, str) or not re.fullmatch('[a-f0-9]{64}', input_sha256):
            raise ValueError('Expected source upload SHA-256')
        sources, purposes = deepcopy(list(sources)), list(purposes)
        if not 1 <= len(sources) <= 5 or not purposes or len(purposes) != len(set(purposes)) or set(purposes) - {'LINE', 'CONTINUUM'}:
            raise ValueError('Expected 1–5 sources and unique LINE/CONTINUUM purposes')
        if any(not isinstance(s, dict) for s in sources):
            raise ValueError('Expected parsed source records')
        ids = [s.get('source_id') for s in sources]
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('Source IDs must be nonempty and unique within a batch')
        if any(s.get('is_valid') is not True for s in sources):
            raise ValueError('Only validated source rows can be retained')
        batch_id = uuid4().hex
        manifest = dict(schema_version='batch_manifest_1', batch_id=batch_id,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        input_sha256=input_sha256, shared_setup=deepcopy(shared_setup), sources=[])
        for source in sources:
            manifest['sources'].append(dict(source=source, source_id=source['source_id'],
                reports=[dict(purpose=p, state='PENDING', run_id=None, error=None) for p in purposes]))
        signature = hashlib.sha256(json.dumps(
            {k: v for k, v in manifest.items() if k not in {'batch_id', 'created_at'}},
            sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
        reserved_size = 0
        if reserve_execution:
            reserved = deepcopy(manifest)
            for source in reserved['sources']:
                for report in source['reports']:
                    # Execution stores short generic ASCII errors, never raw exceptions.
                    report.update(state='COMPLETED', run_id='0' * 65, error='x' * 128)
            reserved_size = self._size(reserved)
        size = max(self._size(manifest), reserved_size)
        if size > self._max_bytes:
            raise ValueError('Batch manifest exceeds retention byte budget')
        with self._lock:
            self.prune()
            if self._closed:
                raise ValueError('Batch store is closed')
            previous = self._submissions.get((owner, submission_token)) if submission_token else None
            if previous is not None:
                if self._records[previous]['signature'] != signature:
                    raise ValueError('Submission token already used with different inputs')
                return previous
            victims = []
            count, total = len(self._records) + 1, sum(i['size'] for i in self._records.values()) + size
            for key, item in self._records.items():
                if count <= self._max_batches and total <= self._max_bytes:
                    break
                if self._finished(item['manifest']):
                    victims.append(key)
                    count -= 1
                    total -= item['size']
            if count > self._max_batches or total > self._max_bytes:
                raise ValueError('Batch retention budget is occupied by active batches')
            for key in victims:
                self._remove(key)
            self._records[batch_id] = dict(owner=owner, manifest=manifest, size=size,
                                          reserved_size=reserved_size, claimed=False,
                                          submission_token=submission_token, signature=signature,
                                          expires_at=self._clock() + self._runs.max_age)
            if submission_token is not None:
                self._submissions[(owner, submission_token)] = batch_id
        return batch_id

    def _owned(self, batch_id, owner):
        self.prune()
        item = self._records.get(batch_id)
        return item if item is not None and item['owner'] == owner else None

    def claim_execution(self, batch_id, owner):
        """Atomically grant one execution attempt for a retained batch."""
        with self._lock:
            item = self._owned(batch_id, owner)
            if item is None:
                raise KeyError('Batch unavailable')
            if item['claimed'] or any(r['state'] != 'PENDING'
                                      for s in item['manifest']['sources'] for r in s['reports']):
                return False
            item['claimed'] = True
            return True

    def update(self, batch_id, owner, source_id, purpose, state, *, run_id=None, error=None):
        """Record one branch transition; terminal results cannot be overwritten."""
        if state not in {'RUNNING', *TERMINAL}:
            raise ValueError('Unsupported execution state')
        if (state == 'COMPLETED') != (isinstance(run_id, str) and bool(run_id)):
            raise ValueError('Only completed branches require a run ID')
        if state != 'COMPLETED' and run_id is not None:
            raise ValueError('Only completed branches may reference a report')
        if error is not None and (state != 'FAILED' or not isinstance(error, str) or len(error) > 2000):
            raise ValueError('Failure detail must be text of at most 2000 characters')
        with self._lock:
            item = self._owned(batch_id, owner)
            if item is None:
                raise KeyError('Batch unavailable')
            manifest = deepcopy(item['manifest'])
            source = next((s for s in manifest['sources'] if s['source_id'] == source_id), None)
            report = next((r for r in source['reports'] if r['purpose'] == purpose), None) if source else None
            if report is None:
                raise ValueError('Unknown source or purpose')
            updated = dict(purpose=purpose, state=state, run_id=run_id, error=error)
            if report == updated:
                return
            if report['state'] in TERMINAL:
                raise ValueError('Terminal branch cannot be replaced')
            if run_id is not None:
                if run_id in self._reverse:
                    raise ValueError('Report already belongs to a batch branch')
                if self._runs.unavailable_reason(run_id) is not None:
                    raise ValueError('Cannot attach an unavailable report')
            report.update(updated)
            size = self._size(manifest)
            if not self._finished(manifest):
                size = max(size, item['reserved_size'])
            if sum(i['size'] for i in self._records.values()) - item['size'] + size > self._max_bytes:
                raise ValueError('Batch manifest exceeds retention byte budget')
            item.update(manifest=manifest, size=size)
            if run_id is not None:
                self._reverse[run_id] = (batch_id, source_id, purpose)

    def get(self, batch_id, owner):
        """Read a detached snapshot with current report availability, no science."""
        with self._lock:
            item = self._owned(batch_id, owner)
            if item is None:
                return None
            manifest = deepcopy(item['manifest'])
            for source in manifest['sources']:
                for report in source['reports']:
                    report['availability'] = (self._runs.unavailable_reason(report['run_id']) or 'AVAILABLE'
                                              if report['run_id'] else 'NO_REPORT')
            manifest['execution_complete'] = self._finished(manifest)
            manifest['retention_policy'] = 'BATCH_REPORTS_PROTECTED_UNTIL_EXPIRY'
            manifest['storage_budget'] = self._runs.retention_budget()
            return manifest

    def lookup_run(self, run_id, owner):
        """Resolve report navigation only within the owning browser scope."""
        with self._lock:
            self.prune()
            link = self._reverse.get(run_id)
            if link is None or self._owned(link[0], owner) is None:
                return None
            return dict(batch_id=link[0], source_id=link[1], purpose=link[2])

    def summaries(self, batch_ids, owner):
        """Return only explicitly supplied owned history IDs, never all batches."""
        result = []
        for batch_id in dict.fromkeys(batch_ids):
            manifest = self.get(batch_id, owner)
            if manifest is not None:
                result.append(dict(batch_id=batch_id, created_at=manifest['created_at'],
                                   source_count=len(manifest['sources']),
                                   execution_complete=manifest['execution_complete']))
        return result
