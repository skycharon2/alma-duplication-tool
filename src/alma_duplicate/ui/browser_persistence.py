"""Persistent reports owned by an anonymous browser session."""
from contextvars import ContextVar
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
from secrets import token_hex
from time import monotonic
import weakref

from flask import abort, request, session
from sqlalchemy import String, cast, or_, select, type_coerce
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from alma_duplicate.artifacts.base import Artifact, FILES
from alma_duplicate.artifacts.cleanup import register_browser_artifact_cleanup
from alma_duplicate.artifacts.local import LocalArtifactStore
from alma_duplicate.persistence.db import database_engine, transaction
from alma_duplicate.persistence.models import (
    assessment_input_links, assessment_input_snapshots, browser_batches, browser_reports,
)
from alma_duplicate.persistence.reports import SavedReportArtifacts
from alma_duplicate.persistence.repositories import RecordUnavailable
from alma_duplicate.ui.batch_store import BatchStore
from alma_duplicate.ui.input_snapshot_storage import insert_input_snapshot, read_input_snapshot
from alma_duplicate.ui.report_management import assessment_is_active, register_report_management
from alma_duplicate.ui.run_store import DownloadLease, RunStore

_owner = ContextVar('browser_report_owner', default=None)


class BrowserRuns:
    """Index completed reports in PostgreSQL and retain immutable file bundles."""

    def __init__(self, engine, store, *, max_runs, max_bytes, max_age, directory):
        self.engine, self.store = engine, store
        self.max_age = max_age
        self.staging_config = dict(max_runs=max_runs, max_bytes=max_bytes,
                                   max_age=max_age, directory=directory)
        self.batches = BrowserBatches(self, clock=monotonic)

    def add(self, request_document, result, *, protect=False):
        return self.add_group([(request_document, result)], protect=protect)[0]

    def add_group(self, assessments, *, protect=False, input_snapshot=None, upload=None,
                  source_labels=None, failed_branches=(), pair_purposes=False):
        owner = _owner.get()
        if owner is None:
            raise ValueError('Missing browser scope')
        assessments = list(assessments)
        staging = RunStore(**self.staging_config)
        try:
            ids = staging.add_group(assessments)
            navigation = {}
            if source_labels is not None:
                navigation = dict(source_reports=list(zip(ids, source_labels, strict=True)),
                                  failed_branches=list(failed_branches))
            elif pair_purposes:
                navigation = dict(purpose_pair=ids)
            metadata = []
            for run_id, (_, result) in zip(ids, assessments, strict=True):
                directory = staging.directory / run_id
                artifacts = self.store.put_bundle({
                    kind: directory / name for kind, name in FILES.items()
                    if (directory / name).is_file()
                })
                overview = staging.overview(run_id)
                overview['listing'] = staging.summaries([run_id])[0]
                if navigation:
                    overview['assessment_navigation'] = navigation
                if source_labels is not None:
                    overview['show_in_history'] = run_id == ids[0]
                metadata.append(dict(id=run_id, owner_digest=owner,
                    assessment_group_id=ids[0],
                    assessment_status=str(result.status), overview=overview,
                    artifact_manifest=[asdict(artifact) for artifact in artifacts]))
            with transaction(self.engine) as db:
                db.execute(browser_reports.insert(), metadata)
                if input_snapshot is not None:
                    snapshot_id = insert_input_snapshot(db, self.store, owner, input_snapshot, upload)
                    db.execute(assessment_input_links.insert(),
                               [dict(report_id=run_id, snapshot_id=snapshot_id) for run_id in ids])
            return ids
        except SQLAlchemyError:
            raise ValueError('Could not save report metadata in the database') from None
        finally:
            staging.close()

    def input_for_report(self, run_id):
        return read_input_snapshot(self.engine, self.store, _owner.get(), browser_reports, run_id)

    def input_for_batch(self, batch_id):
        return read_input_snapshot(self.engine, self.store, _owner.get(), browser_batches, batch_id)

    def _report(self, run_id):
        owner = _owner.get()
        if owner is None:
            return None
        with transaction(self.engine) as db:
            row = db.execute(select(browser_reports).where(
                browser_reports.c.id == run_id,
                browser_reports.c.owner_digest == owner,
                assessment_is_active(browser_reports))).mappings().first()
            return dict(row) if row else None

    def _saved(self, run_id):
        row = self._report(run_id)
        if row is None:
            return None
        artifacts = {record['kind']: Artifact(**record) for record in row['artifact_manifest']}
        return SavedReportArtifacts(self.store,
            dict(id=row['id'], assessment_status=row['assessment_status']), artifacts)

    def page(self, run_id, page=1, view='matches'):
        try:
            saved = self._saved(run_id)
            return saved.page(page, view) if saved is not None else None
        except (RecordUnavailable, OSError, ValueError, KeyError):
            return None

    def queue_page(self, run_id, page=1, view='matches'):
        try:
            saved = self._saved(run_id)
            return saved.queue_page(page, view) if saved is not None else None
        except (RecordUnavailable, OSError, ValueError, KeyError):
            return None

    def open_download(self, run_id, kind):
        try:
            saved = self._saved(run_id)
            if saved is not None:
                stream = saved.open_download(kind)
                return DownloadLease(stream, saved.artifacts[kind].byte_size, lambda: None)
        except (RecordUnavailable, OSError, ValueError, KeyError):
            return None

    def overview(self, run_id):
        row = self._report(run_id)
        return row['overview'] if row else None

    def assessment_navigation(self, run_id):
        overview = self.overview(run_id)
        return overview.get('assessment_navigation') if overview else None

    def history_page(self, *, limit, hidden_report_ids, cursors=None):
        """Read the next older slice of each browser-owned history list."""
        owner = _owner.get()
        if owner is None:
            return [], [], None

        def older_rows(db, columns, payload, *filters, cursor):
            if cursors is not None and cursor is None:
                return []
            # SQLite stores both second and microsecond precision values. Keep
            # the original spelling so an equal timestamp stays equal.
            sqlite = db.dialect.name == 'sqlite'
            created = columns.created_at
            cursor_time = cast(created, String) if sqlite else created
            query = select(columns.id, payload, cursor_time).where(
                columns.owner_digest == owner, *filters)
            if cursor is not None:
                timestamp, run_id = cursor
                boundary = type_coerce(created, String) if sqlite else created
                if not sqlite:
                    timestamp = datetime.fromisoformat(timestamp)
                query = query.where(or_(
                    boundary < timestamp,
                    (boundary == timestamp) & (columns.id < run_id),
                ))
            return db.execute(query.order_by(
                columns.created_at.desc(), columns.id.desc(),
            ).limit(limit + 1)).all()

        reports, batches = browser_reports.c, browser_batches.c
        listed = reports.overview['show_in_history'].as_boolean()
        report_cursor, batch_cursor = cursors or (None, None)
        with self.engine.connect() as db:
            report_rows = older_rows(db, reports, reports.overview, reports.batch_id.is_(None),
                or_(listed.is_(True), listed.is_(None) & reports.id.not_in(hidden_report_ids)),
                assessment_is_active(browser_reports),
                cursor=report_cursor)
            batch_rows = older_rows(db, batches, batches.manifest,
                                    assessment_is_active(browser_batches), cursor=batch_cursor)
        def next_boundary(rows):
            if len(rows) <= limit:
                return None
            entry_id, _, timestamp = rows[limit - 1]
            return (timestamp if isinstance(timestamp, str) else timestamp.isoformat(), entry_id)

        next_cursors = tuple(next_boundary(rows) for rows in (report_rows, batch_rows))
        return (
            [overview['listing'] for _, overview, _ in report_rows[:limit]],
            [dict(batch_id=batch_id, created_at=manifest['created_at'],
                  source_count=len(manifest['sources']),
                  execution_complete=manifest['execution_complete'])
             for batch_id, manifest, _ in batch_rows[:limit]],
            next_cursors if any(next_cursors) else None,
        )

    def reusable_assessment_ids(self, report_ids, batch_ids):
        """Find linked snapshots without opening uploads on the report listing."""
        owner = _owner.get()
        if owner is None or not (report_ids or batch_ids):
            return set()
        links = assessment_input_links
        snapshots = assessment_input_snapshots
        with self.engine.connect() as db:
            rows = db.execute(
                select(links.c.report_id, links.c.batch_id)
                .join(snapshots, snapshots.c.id == links.c.snapshot_id)
                .where(snapshots.c.owner_digest == owner,
                       or_(links.c.report_id.in_(report_ids), links.c.batch_id.in_(batch_ids)))
            )
            return {report_id or batch_id for report_id, batch_id in rows}

    def unavailable_reason(self, run_id):
        return None if self._report(run_id) is not None else 'UNKNOWN'

    def retention_budget(self):
        return None

    def prune(self):
        self.batches.prune()

    def close(self):
        self.batches.close()


class BrowserBatches(BatchStore):
    """Keep execution state in memory and persist completed manifests."""

    def _authorized(self, owner):
        return isinstance(owner, str) and sha256(owner.encode()).hexdigest() == _owner.get()

    def save_completed(self, batch_id, owner, *, input_snapshot=None, upload=None):
        manifest = super().get(batch_id, owner)
        if not self._authorized(owner) or not manifest or not manifest['execution_complete']:
            return
        digest = _owner.get()
        try:
            with transaction(self._runs.engine) as db:
                insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
                created = db.execute(insert(browser_batches).values(
                    id=batch_id, owner_digest=digest, manifest=manifest
                ).on_conflict_do_nothing(index_elements=['id']).returning(browser_batches.c.id)).scalar_one_or_none()
                if created is None:
                    return
                if input_snapshot is not None:
                    snapshot_id = insert_input_snapshot(db, self._runs.store, digest, input_snapshot, upload)
                    db.execute(assessment_input_links.insert().values(batch_id=batch_id, snapshot_id=snapshot_id))
                ids = [r['run_id'] for s in manifest['sources'] for r in s['reports'] if r['run_id']]
                if ids:
                    updated = db.execute(browser_reports.update().where(
                        browser_reports.c.id.in_(ids), browser_reports.c.owner_digest == digest,
                        browser_reports.c.batch_id.is_(None)).values(batch_id=batch_id))
                    if updated.rowcount != len(ids):
                        raise ValueError('Batch report ownership mismatch')
        except SQLAlchemyError:
            raise ValueError('Could not save batch metadata in the database') from None

    def get(self, batch_id, owner):
        if not self._authorized(owner):
            return None
        with transaction(self._runs.engine) as db:
            row = db.execute(select(browser_batches.c.manifest,
                                    assessment_is_active(browser_batches)).where(
                browser_batches.c.id == batch_id,
                browser_batches.c.owner_digest == _owner.get())).first()
        if row is not None:
            manifest, active = row
            return manifest if active else None
        manifest = super().get(batch_id, owner)
        return manifest if manifest is not None and not manifest['execution_complete'] else None

    def lookup_run(self, run_id, owner):
        if not self._authorized(owner):
            return None
        entry = self._runs._report(run_id)
        if entry is None:
            return None
        batch_id = entry['batch_id']
        if not batch_id:
            return super().lookup_run(run_id, owner)
        manifest = self.get(batch_id, owner)
        for source in (manifest or {}).get('sources', []):
            for report in source['reports']:
                if report['run_id'] == run_id:
                    return dict(batch_id=batch_id, source_id=source['source_id'], purpose=report['purpose'])
        return None


def register_browser_persistence(app):
    secret = app.config.get('BROWSER_SESSION_SECRET')
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError('BROWSER_SESSION_SECRET must contain at least 32 characters')
    if not app.config.get('ARTIFACT_ROOT'):
        raise ValueError('ARTIFACT_ROOT is required for database report storage')
    engine = app.config.get('BROWSER_TEST_ENGINE') if app.testing else None
    if engine is None:
        if not app.config.get('DATABASE_URL'):
            raise ValueError('DATABASE_URL is required for database report storage')
        engine = database_engine(app.config['DATABASE_URL'])
        weakref.finalize(app, engine.dispose)
    app.config.update(SECRET_KEY=secret, SESSION_COOKIE_NAME='alma_browser_reports',
                      SESSION_COOKIE_SECURE=app.config['BROWSER_COOKIE_SECURE'])
    runs = BrowserRuns(engine, LocalArtifactStore(Path(app.config['ARTIFACT_ROOT'])),
        max_runs=app.config['MAX_RETAINED_RUNS'], max_bytes=app.config['MAX_RETAINED_BYTES'],
        max_age=app.config['MAX_RUN_AGE_SECONDS'], directory=app.config['RUN_STORAGE_PARENT'])

    @app.before_request
    def browser_scope():
        if request.endpoint in {'static', 'healthz'} or request.endpoint is None:
            return
        if request.method == 'POST' and request.headers.get('Sec-Fetch-Site') == 'cross-site':
            abort(403)
        token = session.get('batch_owner')
        if not isinstance(token, str) or re.fullmatch('[a-f0-9]{48}', token) is None:
            token = token_hex(24)
            session['batch_owner'] = token
        session.permanent = True
        request.environ['alma.browser-report-owner'] = _owner.set(sha256(token.encode()).hexdigest())

    @app.teardown_request
    def clear_browser_scope(_error):
        reset = request.environ.pop('alma.browser-report-owner', None)
        if reset is not None:
            _owner.reset(reset)

    register_report_management(app, engine, _owner.get)
    register_browser_artifact_cleanup(app, engine, runs.store)
    return runs
