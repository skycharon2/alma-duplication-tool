"""Browser-owned trash transitions and visibility rules."""
from datetime import datetime, timedelta, timezone
import os
from secrets import compare_digest, token_hex

import click
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.models import (
    assessment_input_links, assessment_input_snapshots,
    browser_artifact_cleanup, browser_assessment_trash, browser_batches, browser_reports,
)


def _trash_match(parent):
    columns = parent.c
    if parent is browser_reports:
        kind = case((columns.batch_id.is_not(None), 'BATCH'), else_='REPORT')
        identity = func.coalesce(columns.batch_id, columns.assessment_group_id, columns.id)
    else:
        kind, identity = 'BATCH', columns.id
    trash = browser_assessment_trash.c
    return ((trash.owner_digest == columns.owner_digest)
            & (trash.assessment_kind == kind) & (trash.assessment_id == identity))


def assessment_is_active(parent):
    return ~select(browser_assessment_trash.c.assessment_id).where(
        _trash_match(parent)).correlate(parent).exists()


def _assessment_name(kind, payload):
    if kind == 'batch':
        return payload.get('name') or f"Multi-source assessment · {len(payload['sources'])} targets"
    return payload['listing']['target']


def _utc(timestamp):
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _lock_assessment(db, owner, kind, entry_id, *, group=False):
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    if kind == 'batch':
        columns = browser_batches.c
        query = select(columns.id).where(columns.id == entry_id, columns.owner_digest == owner)
    else:
        columns = browser_reports.c
        identity = func.coalesce(columns.assessment_group_id, columns.id)
        if not group:
            member = browser_reports.alias('requested_member').c
            entry_id = select(func.coalesce(member.assessment_group_id, member.id)).where(
                member.owner_digest == owner, member.id == entry_id, member.batch_id.is_(None),
            ).scalar_subquery()
        query = select(identity).where(
            columns.owner_digest == owner, columns.batch_id.is_(None), identity == entry_id,
        ).order_by(columns.id).limit(1)
    return db.scalar(query.with_for_update())


def _remove_trash(db, owner, kind, assessment_id, *, cutoff=None):
    trash = browser_assessment_trash
    statement = trash.delete().where(
        trash.c.owner_digest == owner, trash.c.assessment_kind == kind.upper(),
        trash.c.assessment_id == assessment_id,
    )
    if cutoff is not None:
        statement = statement.where(trash.c.purge_after <= cutoff)
    return db.scalar(statement.returning(trash.c.assessment_id))


def purge_assessment(db, owner, kind, assessment_id, insert):
    reports, batches = browser_reports, browser_batches
    report_scope = (reports.c.owner_digest == owner)
    if kind == 'batch':
        report_scope &= reports.c.batch_id == assessment_id
    else:
        report_scope &= reports.c.batch_id.is_(None) & (
            func.coalesce(reports.c.assessment_group_id, reports.c.id) == assessment_id)
    report_scope = select(reports.c.id).where(report_scope)

    links, snapshots = assessment_input_links, assessment_input_snapshots
    selected_links = links.c.report_id.in_(report_scope)
    if kind == 'batch':
        selected_links = or_(selected_links, links.c.batch_id == assessment_id)
    snapshot_ids = db.scalars(select(snapshots.c.id).where(
        snapshots.c.owner_digest == owner,
        snapshots.c.id.in_(select(links.c.snapshot_id).where(selected_links)),
    ).order_by(snapshots.c.id).with_for_update()).all()
    db.execute(links.delete().where(selected_links))
    manifests = db.scalars(reports.delete().where(
        reports.c.id.in_(report_scope)).returning(reports.c.artifact_manifest)).all()
    files = {item['storage_key']: item['kind'] for manifest in manifests for item in manifest}
    if kind == 'batch':
        db.execute(batches.delete().where(
            batches.c.owner_digest == owner, batches.c.id == assessment_id))
    uploads = db.scalars(snapshots.delete().where(
        snapshots.c.owner_digest == owner, snapshots.c.id.in_(snapshot_ids),
        ~select(links.c.id).where(links.c.snapshot_id == snapshots.c.id)
        .correlate(snapshots).exists(),
    ).returning(snapshots.c.upload)).all()
    for upload in uploads:
        if upload is not None:
            artifact = upload['artifact']
            files[artifact['storage_key']] = artifact['kind']
    queue = browser_artifact_cleanup
    if files:
        db.execute(insert(queue).on_conflict_do_nothing(index_elements=[queue.c.storage_key]), [
            dict(storage_key=key, kind=files[key]) for key in sorted(files)
        ])


def register_report_management(app, engine, current_owner):
    days = app.config.get('REPORT_TRASH_RETENTION_DAYS')
    if days is None:
        days = int(os.environ.get('ALMA_REPORT_TRASH_RETENTION_DAYS', '7'))
    if type(days) is not int or days < 1:
        raise ValueError('REPORT_TRASH_RETENTION_DAYS must be a positive integer')
    retention = timedelta(days=days)
    routes = Blueprint('report_management', __name__)
    insert = sqlite_insert if engine.dialect.name == 'sqlite' else pg_insert

    @app.cli.command('purge-expired-browser-assessments')
    @click.option('--limit', type=click.IntRange(1, 500), default=100, show_default=True)
    def purge_expired_browser_assessments(limit):
        """Permanently delete expired trash entries and enqueue their files."""
        cutoff = datetime.now(timezone.utc)
        trash = browser_assessment_trash.c
        with engine.connect() as db:
            candidates = db.execute(select(
                trash.owner_digest, trash.assessment_kind, trash.assessment_id,
            ).where(trash.purge_after <= cutoff).order_by(
                trash.purge_after, trash.owner_digest, trash.assessment_kind, trash.assessment_id,
            ).limit(limit)).all()
        removed = 0
        for owner, kind, assessment_id in candidates:
            kind = kind.lower()
            with transaction(engine) as db:
                target = _lock_assessment(db, owner, kind, assessment_id, group=True)
                if _remove_trash(db, owner, kind, assessment_id, cutoff=cutoff) is not None:
                    if target is not None:
                        purge_assessment(db, owner, kind, assessment_id, insert)
                    removed += 1
        click.echo(f'Expired trash entries removed: {removed}. Run file cleanup to reclaim storage.')

    @app.context_processor
    def trash_token():
        if request.endpoint not in {'report_index', 'report_management.trash_index',
                                    'report_management.confirm_purge'}:
            return {}
        return {'report_management_csrf': session.setdefault('report_management_csrf', token_hex(32))}

    @routes.get('/reports/trash')
    def trash_index():
        page_text = request.args.get('page', '1')
        if len(page_text) > 8 or not page_text.isdecimal() or int(page_text) < 1:
            abort(400)
        page = int(page_text)
        page_size = 20
        trash, report, batch = browser_assessment_trash, browser_reports, browser_batches
        representative = report.alias('representative')
        first_report = select(representative.c.id).where(
            trash.c.assessment_kind == 'REPORT',
            representative.c.owner_digest == trash.c.owner_digest,
            representative.c.batch_id.is_(None),
            func.coalesce(representative.c.assessment_group_id, representative.c.id)
            == trash.c.assessment_id,
        ).order_by(
            case((representative.c.overview['show_in_history'].as_boolean().is_(True), 0), else_=1),
            representative.c.created_at, representative.c.id,
        ).limit(1).correlate(trash).scalar_subquery()
        with engine.connect() as db:
            rows = db.execute(select(
                trash.c.deleted_at, trash.c.purge_after,
                report.c.id, report.c.overview, batch.c.id, batch.c.manifest,
            ).select_from(trash.outerjoin(report, report.c.id == first_report).outerjoin(
                batch, (trash.c.assessment_kind == 'BATCH') & (batch.c.id == trash.c.assessment_id)
                & (batch.c.owner_digest == trash.c.owner_digest),
            )).where(trash.c.owner_digest == current_owner(),
                     or_(report.c.id.is_not(None), batch.c.id.is_not(None))
            ).order_by(trash.c.deleted_at.desc(), trash.c.assessment_kind, trash.c.assessment_id
            ).offset((page - 1) * page_size).limit(page_size + 1)).all()
        if page > 1 and not rows:
            abort(404)
        entries = []
        for deleted_at, purge_after, report_id, overview, batch_id, manifest in rows[:page_size]:
            if manifest is not None:
                kind, entry_id, payload = 'batch', batch_id, manifest
            else:
                kind, entry_id, payload = 'report', report_id, overview
            entries.append(dict(name=_assessment_name(kind, payload), kind=kind,
                                id=entry_id, deleted_at=_utc(deleted_at), purge_after=_utc(purge_after)))
        return render_template('report_trash.html', entries=entries, page=page,
                               has_next=len(rows) > page_size)

    @routes.get('/reports/manage/<kind>/<entry_id>/purge')
    def confirm_purge(kind, entry_id):
        if kind == 'batch':
            parent = browser_batches
            query = select(parent.c.manifest)
        elif kind == 'report':
            parent = browser_reports
            query = select(parent.c.overview).where(parent.c.batch_id.is_(None))
        else:
            abort(404)
        trash = browser_assessment_trash
        with engine.connect() as db:
            row = db.execute(query.add_columns(trash.c.deleted_at).select_from(
                parent.join(trash, _trash_match(parent))).where(
                parent.c.id == entry_id, parent.c.owner_digest == current_owner(),
            )).first()
        if row is None:
            abort(404)
        payload, deleted_at = row
        return render_template('report_purge.html', kind=kind, entry_id=entry_id,
                               name=_assessment_name(kind, payload), deleted_at=_utc(deleted_at))

    @routes.post('/reports/manage/<kind>/<entry_id>/<action>')
    def update_trash(kind, entry_id, action):
        if kind not in {'report', 'batch'} or action not in {'trash', 'restore', 'purge'}:
            abort(404)
        tokens = request.form.getlist('csrf')
        expected = session.get('report_management_csrf')
        if (not expected or len(tokens) != 1 or not tokens[0].isascii()
                or not compare_digest(tokens[0], expected)):
            abort(403)
        if action == 'purge' and request.form.getlist('confirm') != ['yes']:
            abort(400, description='Confirm permanent deletion before continuing.')
        owner = current_owner()
        if owner is None:
            abort(404)

        trash = browser_assessment_trash
        with transaction(engine) as db:
            assessment_id = _lock_assessment(db, owner, kind, entry_id)
            if assessment_id is None:
                abort(404)
            key = dict(owner_digest=owner, assessment_kind=kind.upper(), assessment_id=assessment_id)
            if action == 'trash':
                now = datetime.now(timezone.utc)
                db.execute(insert(trash).values(
                    **key, deleted_at=now, purge_after=now + retention,
                ).on_conflict_do_nothing(index_elements=list(trash.primary_key.columns)))
            else:
                removed = _remove_trash(db, owner, kind, assessment_id)
                if action == 'purge':
                    if removed is None:
                        abort(409, description='Move the assessment to trash before permanently deleting it.')
                    purge_assessment(db, owner, kind, assessment_id, insert)
        if action == 'trash':
            flash('Assessment moved to trash.', 'report-management')
            return redirect(url_for('report_index'), code=303)
        flash('Assessment permanently deleted. File cleanup is queued.' if action == 'purge'
              else 'Assessment restored to Existing reports.', 'report-management')
        return redirect(url_for('report_management.trash_index'), code=303)

    app.register_blueprint(routes)
