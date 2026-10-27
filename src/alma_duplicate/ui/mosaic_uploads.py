"""Session-owned, bounded temporary OT collections for form editing."""
from copy import deepcopy
from secrets import token_hex
from threading import Lock
from time import monotonic


class MosaicUploadStore:
    def __init__(self, *, ttl=3600, capacity=64, clock=monotonic):
        self.ttl, self.capacity, self.clock = ttl, capacity, clock
        self.entries = {}
        self.lock = Lock()

    def _expire(self):
        now = self.clock()
        self.entries = {k: v for k, v in self.entries.items() if now-v[0] < self.ttl}

    def put(self, owner, collection):
        with self.lock:
            self._expire()
            if len(self.entries) >= self.capacity:
                raise ValueError('Upload storage is busy. Remove an earlier upload or try again later.')
            token = token_hex(24)
            self.entries[token] = (self.clock(), owner, deepcopy(collection))
            return token

    def get(self, owner, token):
        with self.lock:
            self._expire()
            entry = self.entries.get(token)
            return deepcopy(entry[2]) if entry and entry[1] == owner else None

    def remove(self, owner, token):
        with self.lock:
            entry = self.entries.get(token)
            if entry and entry[1] == owner:
                del self.entries[token]
