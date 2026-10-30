"""Temporary, session-owned Single Pointing drafts sharing one position."""
from collections import OrderedDict
from copy import deepcopy
import json
from threading import RLock
import time
from uuid import uuid4

POSITION = ('ra', 'dec', 'ra_format', 'dec_format')


class ObservationSets:
    def __init__(self):
        self._sets = OrderedDict()
        self._lock = RLock()

    def get(self, key, owner):
        with self._lock:
            for expired in [k for k, v in self._sets.items() if v['expires'] < time.monotonic()]:
                del self._sets[expired]
            value = self._sets.get(key)
            return deepcopy(value) if value and value['owner'] == owner else None

    def put(self, value, expected=None):
        with self._lock:
            old = self._sets.get(value['id'])
            if expected is not None and (old is None or old['revision'] != expected):
                raise ValueError('This observation set changed in another tab. Reload before editing.')
            if len(json.dumps(value)) > 1024 * 1024:
                raise ValueError('Observation set exceeds the temporary storage limit.')
            value = deepcopy(value)
            value['revision'] += 1
            value['expires'] = time.monotonic() + 3600
            self._sets[value['id']] = value
            self._sets.move_to_end(value['id'])
            while len(self._sets) > 32:
                self._sets.popitem(last=False)
            return deepcopy(value)

    def create(self, owner, values, rows):
        item = {'id': uuid4().hex, 'owner': owner, 'revision': 0,
                'active': '1', 'position': {}, 'observations': []}
        item['observations'].append({'id': '1', 'label': 'Observation 1',
                                     'values': {}, 'rows': [], 'reports': []})
        self.save_draft(item, values, rows)
        return self.put(item)

    def append_report(self, key, owner, observation_id, report_id):
        with self._lock:
            group = self.get(key, owner)
            if group is None:
                return
            current = next(o for o in group['observations'] if o['id'] == observation_id)
            current['reports'] = (current['reports'] + [report_id])[-8:]
            self.put(group, expected=group['revision'])

    @staticmethod
    def save_draft(group, values, rows):
        if values.get('geometry', 'SINGLE_POINTING') != 'SINGLE_POINTING' or values.get('target_kind', 'FIXED') != 'FIXED':
            raise ValueError('Shared-position observation sets require fixed Single Pointing inputs.')
        group['position'] = {k: values.get(k, 'DEG' if k.endswith('_format') else '') for k in POSITION}
        current = next(o for o in group['observations'] if o['id'] == group['active'])
        current['values'] = {k: deepcopy(v) for k, v in values.items()
                             if k not in ('action', 'observation_group', 'observation_revision')}
        current['rows'] = list(rows)

    @staticmethod
    def load_draft(group):
        current = next(o for o in group['observations'] if o['id'] == group['active'])
        values = deepcopy(current['values']) | group['position']
        values.update(observation_group=group['id'], observation_revision=str(group['revision']),
                      observation_active=group['active'])
        return values, list(current['rows'])

    @staticmethod
    def add(group):
        if len(group['observations']) >= 8:
            raise ValueError('At most eight observations can share this position.')
        current = next(o for o in group['observations'] if o['id'] == group['active'])
        added = deepcopy(current)
        added['id'] = str(len(group['observations']) + 1)
        added['label'] = 'Observation ' + added['id']
        added['reports'] = []
        added['values']['setup_id'] = 'setup-' + added['id']
        group['observations'].append(added)
        group['active'] = added['id']
