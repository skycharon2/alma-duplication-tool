"""Workspace-scoped metadata access inside a caller-owned transaction.

The caller must authorize workspace access before construction. No methods
commit, query scientific sources, write files or publish a report as ready.
"""
from copy import deepcopy
import json
import math
import re
from uuid import uuid4

from sqlalchemy import select, func
from alma_duplicate.parsers.source_list import MAX_SOURCES
from alma_duplicate.persistence import models as m


class RecordUnavailable(LookupError):
    """Missing and other-workspace records are intentionally indistinguishable."""


class StaleAttempt(ValueError):
    """Run metadata cannot be recorded for an inactive or superseded attempt."""


def _text(value, limit, name):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {name}')
    return value


def _digest(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Expected a lowercase SHA-256 digest')
    return value


def _json(value):
    if not isinstance(value, dict):
        raise ValueError('Expected metadata object')
    raw = json.dumps(value, allow_nan=False, ensure_ascii=False)
    if len(raw.encode('utf-8')) > 1_000_000:
        raise ValueError('Metadata exceeds one million bytes')
    return json.loads(raw)


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Invalid {name}')
    return value


class WorkspaceRepository:
    def __init__(self, session, workspace_id):
        self.session = session
        self.workspace_id = _text(workspace_id, 65, 'workspace ID')

    def _query(self, table):
        return select(table).where(table.c.workspace_id == self.workspace_id)

    def _get(self, table, identity):
        row = self.session.execute(self._query(table).where(table.c.id == identity)).mappings().first()
        if row is None:
            raise RecordUnavailable('Record unavailable')
        return deepcopy(dict(row))

    def get_submission(self, identity):
        return self._get(m.submissions, identity)

    def get_source(self, identity):
        return self._get(m.sources, identity)

    def get_job(self, identity):
        return self._get(m.jobs, identity)

    def get_run(self, identity):
        return self._get(m.runs, identity)

    def list_submissions(self, *, limit=50, offset=0):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError('Invalid page bounds')
        rows = self.session.execute(self._query(m.submissions).order_by(
            m.submissions.c.created_at.desc(), m.submissions.c.id.desc()).limit(limit).offset(offset)).mappings()
        return [deepcopy(dict(row)) for row in rows]

    def sources_for_submission(self, identity):
        self.get_submission(identity)
        rows = self.session.execute(self._query(m.sources).where(
            m.sources.c.submission_id == identity).order_by(m.sources.c.ordinal)).mappings()
        return [deepcopy(dict(row)) for row in rows]

    def jobs_for_submission(self, identity):
        self.get_submission(identity)
        rows = self.session.execute(self._query(m.jobs).join(m.sources,
            (m.jobs.c.source_id == m.sources.c.id) &
            (m.jobs.c.workspace_id == m.sources.c.workspace_id)).where(
            m.jobs.c.submission_id == identity).order_by(m.sources.c.ordinal, m.jobs.c.purpose)).mappings()
        return [deepcopy(dict(row)) for row in rows]

    def create_submission(self, *, kind, settings, input_sha256, sources, purposes,
                          queue_snapshot_key=None, queue_snapshot_sha256=None):
        """Insert one submission, ordered sources and pending jobs; never commit.

        Run-again creates another submission; source names are not deduplication
        keys. On any database error the caller must roll back the transaction.
        """
        if kind not in ('SINGLE', 'MULTI', 'MOSAIC'):
            raise ValueError('Invalid submission kind')
        settings, input_sha256 = _json(settings), _digest(input_sha256)
        if (queue_snapshot_key is None) != (queue_snapshot_sha256 is None):
            raise ValueError('Snapshot key and digest must be supplied together')
        if queue_snapshot_key is not None:
            _text(queue_snapshot_key, 512, 'snapshot key')
            _digest(queue_snapshot_sha256)
        purposes, sources = list(purposes), list(sources)
        if not purposes or len(set(purposes)) != len(purposes) or set(purposes) - {'LINE', 'CONTINUUM'}:
            raise ValueError('Expected unique scientific purposes')
        if not sources or len(sources) > (MAX_SOURCES if kind == 'MULTI' else 1):
            raise ValueError('Invalid source count')
        prepared = []
        submission_id = uuid4().hex
        for ordinal, source in enumerate(sources):
            if set(source) - {'name', 'ra_deg', 'dec_deg', 'redshift', 'original_input'}:
                raise ValueError('Unknown source fields')
            ra, dec = _number(source['ra_deg'], 'RA'), _number(source['dec_deg'], 'Dec')
            z = source.get('redshift')
            if not 0 <= ra < 360 or not -90 <= dec <= 90:
                raise ValueError('Invalid ICRS coordinates')
            if z is not None and not -1 < _number(z, 'redshift') < 1e308:
                raise ValueError('Invalid redshift')
            prepared.append(dict(id=uuid4().hex, workspace_id=self.workspace_id,
                submission_id=submission_id, ordinal=ordinal, name=_text(source['name'], 255, 'source name'),
                ra_deg=ra, dec_deg=dec, redshift=z, original_input=_json(source['original_input'])))
        self.session.execute(m.submissions.insert().values(id=submission_id, workspace_id=self.workspace_id,
            kind=kind, settings=settings, input_sha256=input_sha256,
            queue_snapshot_key=queue_snapshot_key, queue_snapshot_sha256=queue_snapshot_sha256))
        for source in prepared:
            self.session.execute(m.sources.insert().values(**source))
            for purpose in purposes:
                self.session.execute(m.jobs.insert().values(id=uuid4().hex, workspace_id=self.workspace_id,
                    submission_id=submission_id, source_id=source['id'], purpose=purpose))
        return submission_id

    def record_run(self, job_id, *, attempt, lease_token, report_schema, assessment_status, source_provenance):
        """Append metadata for a valid leased attempt; not artifact publication.

        Lock the job until the enclosing transaction ends. Recovery/claim code
        must update that same row; an expired token cannot publish a new run.
        Duplicate attempts fail the database uniqueness constraint, never overwrite.
        """
        if type(attempt) is not int or attempt < 1:
            raise ValueError('Invalid attempt')
        _text(lease_token, 65, 'lease token')
        report_schema = _text(report_schema, 128, 'report schema')
        assessment_status = _text(assessment_status, 64, 'assessment status')
        source_provenance = _json(source_provenance)
        locked = self.session.execute(self._query(m.jobs).where(
            m.jobs.c.id == job_id).with_for_update()).first()
        if locked is None:
            raise RecordUnavailable('Record unavailable')
        # PostgreSQL CURRENT_TIMESTAMP is frozen at transaction start. A lease
        # must be checked against actual database time even in a long transaction.
        clock = (func.clock_timestamp() if self.session.get_bind().dialect.name == 'postgresql'
                 else func.current_timestamp())
        live = self.session.execute(self._query(m.jobs).where(
            m.jobs.c.id == job_id, m.jobs.c.state == 'RUNNING', m.jobs.c.attempt == attempt,
            m.jobs.c.lease_token == lease_token, m.jobs.c.lease_expires_at > clock
        )).first()
        if live is None:
            raise StaleAttempt('Job attempt is not active')
        run_id = uuid4().hex
        self.session.execute(m.runs.insert().values(id=run_id, workspace_id=self.workspace_id,
            job_id=job_id, attempt=attempt, report_schema=report_schema,
            assessment_status=assessment_status, source_provenance=source_provenance))
        return run_id
