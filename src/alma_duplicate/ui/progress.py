"""Bounded, process-local progress snapshots for concurrent browser requests."""
from copy import deepcopy
from threading import Lock
from time import monotonic


class ProgressStore:
    def __init__(self, *, limit=64, max_active=4, ttl=1800, clock=monotonic):
        self._items = {}
        self._lock = Lock()
        self._limit, self._max_active, self._ttl, self._clock = limit, max_active, ttl, clock

    def _prune(self):
        now = self._clock()
        for key, (updated, state) in list(self._items.items()):
            if state['status'] != 'RUNNING' and now - updated >= self._ttl:
                del self._items[key]

    def begin(self, token):
        with self._lock:
            self._prune()
            if token in self._items:
                return False
            if sum(s['status'] == 'RUNNING' for _, s in self._items.values()) >= self._max_active:
                return False
            while len(self._items) >= self._limit:
                oldest = next((key for key, (_, s) in self._items.items() if s['status'] != 'RUNNING'), None)
                if oldest is None:
                    return False
                del self._items[oldest]
            self._items[token] = (self._clock(), {'status': 'RUNNING', 'stage': 'validation', 'stages': {}})
            return True

    def update(self, token, event):
        with self._lock:
            item = self._items.get(token)
            if item is None or item[1]['status'] != 'RUNNING':
                return
            state = item[1]
            state['stage'] = event['stage']
            state['stages'][event['stage']] = dict(event)
            self._items[token] = self._clock(), state

    def finish(self, token, *, report_url=None):
        with self._lock:
            item = self._items.get(token)
            if item is not None:
                state = item[1]
                state['status'] = 'COMPLETED' if report_url else 'FAILED'
                if report_url:
                    state['report_url'] = report_url
                self._items[token] = self._clock(), state

    def get(self, token):
        with self._lock:
            self._prune()
            item = self._items.get(token)
            return deepcopy(item[1]) if item else None
