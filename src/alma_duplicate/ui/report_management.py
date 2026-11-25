"""Browser-owned trash transitions and visibility rules."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import re
from secrets import compare_digest, token_hex

import click
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import case, func, literal, or_, select, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.models import (
    assessment_input_links, assessment_input_snapshots,
    browser_artifact_cleanup, browser_assessment_labels, browser_assessment_trash,
    browser_batches, browser_reports,
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


def _storage_rows(db, owner, *, groups=None, batch_ids=None):
    reports, batches = browser_reports, browser_batches
    links, snapshots = assessment_input_links, assessment_input_snapshots

    def with_upload(parent, parent_link):
        return parent.outerjoin(links, parent_link == parent.c.id).outerjoin(
            snapshots, (snapshots.c.id == links.c.snapshot_id) & (snapshots.c.owner_digest == owner))

    report_rows = select(case((reports.c.batch_id.is_not(None), 'BATCH'), else_='REPORT'),
               func.coalesce(reports.c.batch_id, reports.c.assessment_group_id, reports.c.id),
               assessment_is_active(reports), reports.c.artifact_manifest, snapshots.c.upload
        ).select_from(with_upload(reports, links.c.report_id)).where(reports.c.owner_digest == owner)
    batch_rows = select(literal('BATCH'), batches.c.id, assessment_is_active(batches), literal(None),
               snapshots.c.upload
        ).select_from(with_upload(batches, links.c.batch_id)).where(batches.c.owner_digest == owner)
    if groups is not None:
        report_rows = report_rows.where(or_(
            reports.c.batch_id.in_(batch_ids),
            reports.c.batch_id.is_(None) & or_(
                reports.c.assessment_group_id.in_(groups),
                reports.c.assessment_group_id.is_(None) & reports.c.id.in_(groups),
            ),
        ))
        batch_rows = batch_rows.where(batches.c.id.in_(batch_ids))
    for kind, entry_id, active, manifest, upload in db.execute(union_all(report_rows, batch_rows)).yield_per(256):
        descriptors = list(manifest or ())
        if upload:
            descriptors.append(upload['artifact'])
        yield (kind, entry_id), active, descriptors


def assessment_storage_sizes(db, owner, groups, batch_ids):
    if not (groups or batch_ids):
        return {}
    files = {}
    for entry, _, descriptors in _storage_rows(db, owner, groups=groups, batch_ids=batch_ids):
        paths = files.setdefault(entry, {})
        for item in descriptors:
            key = item['storage_key']
            paths[key] = max(paths.get(key, 0), item['byte_size'])
    return {entry: sum(paths.values()) for entry, paths in files.items()}


def _storage_usage(db, owner):
    assessments = {}
    files = {}
    for entry, active, descriptors in _storage_rows(db, owner):
        assessments[entry] = active
        for item in descriptors:
            key, size = item['storage_key'], item['byte_size']
            # Attribute a shared path to active history if any active item uses it.
            previous_size, previously_active = files.get(key, (0, False))
            files[key] = (max(size, previous_size), active or previously_active)
    active_count = sum(assessments.values())
    history_bytes = sum(size for size, active in files.values() if active)
    trash_bytes = sum(size for size, active in files.values() if not active)
    return dict(active_count=active_count, trash_count=len(assessments) - active_count,
                history_bytes=history_bytes, trash_bytes=trash_bytes,
                total_bytes=history_bytes + trash_bytes)


def _display_bytes(size):
    for unit, scale in (('GiB', 1024**3), ('MiB', 1024**2), ('KiB', 1024)):
        if size >= scale:
            return f'{size / scale:,.1f} {unit}'
    return f'{size} B'


def assessment_display_name(parent):
    columns = parent.c
    labels = browser_assessment_labels.c
    kind, identity = ('REPORT', func.coalesce(columns.assessment_group_id, columns.id)
                      ) if parent is browser_reports else ('BATCH', columns.id)
    return select(labels.display_name).where(
        labels.owner_digest == columns.owner_digest, labels.assessment_kind == kind,
        labels.assessment_id == identity,
    ).correlate(parent).scalar_subquery()


def _assessment_name(kind, payload):
    if kind == 'batch':
        return payload.get('name') or f"Multi-source assessment · {len(payload['sources'])} targets"
    return payload['listing']['target']


def _utc(timestamp):
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _trash_snapshot(db, owner):
    trash = browser_assessment_trash.c
    entries = db.execute(select(trash.assessment_kind, trash.assessment_id, trash.deleted_at)
        .where(trash.owner_digest == owner)
        .order_by(trash.assessment_kind, trash.assessment_id)).all()
    identity = [(kind, entry_id, _utc(deleted_at).isoformat())
                for kind, entry_id, deleted_at in entries]
    digest = sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest()
    return entries, digest


def _begin_management_write(db):
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


def _lock_assessment(db, owner, kind, entry_id, *, group=False, begun=False):
    if not begun:
        _begin_management_write(db)
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
    labels = browser_assessment_labels
    db.execute(labels.delete().where(
        labels.c.owner_digest == owner, labels.c.assessment_kind == kind.upper(),
        labels.c.assessment_id == assessment_id,
    ))
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
                                    'report_management.confirm_purge', 'report_management.rename',
                                    'report_management.empty_trash'}:
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
                trash.c.assessment_kind, trash.c.assessment_id, trash.c.deleted_at, trash.c.purge_after,
                report.c.id, report.c.overview, batch.c.id, batch.c.manifest,
            ).select_from(trash.outerjoin(report, report.c.id == first_report).outerjoin(
                batch, (trash.c.assessment_kind == 'BATCH') & (batch.c.id == trash.c.assessment_id)
                & (batch.c.owner_digest == trash.c.owner_digest),
            )).where(trash.c.owner_digest == current_owner(),
                     or_(report.c.id.is_not(None), batch.c.id.is_not(None))
            ).order_by(trash.c.deleted_at.desc(), trash.c.assessment_kind, trash.c.assessment_id
            ).offset((page - 1) * page_size).limit(page_size + 1)).all()
            sizes = assessment_storage_sizes(
                db, current_owner(),
                [row.assessment_id for row in rows[:page_size] if row.assessment_kind == 'REPORT'],
                [row.assessment_id for row in rows[:page_size] if row.assessment_kind == 'BATCH'],
            )
        if page > 1 and not rows:
            abort(404)
        entries = []
        for category, assessment_id, deleted_at, purge_after, report_id, overview, batch_id, manifest in rows[:page_size]:
            if manifest is not None:
                kind, entry_id, payload = 'batch', batch_id, manifest
            else:
                kind, entry_id, payload = 'report', report_id, overview
            entries.append(dict(name=_assessment_name(kind, payload), kind=kind,
                                id=entry_id, deleted_at=_utc(deleted_at), purge_after=_utc(purge_after),
                                saved_bytes=sizes.get((category, assessment_id))))
        return render_template('report_trash.html', entries=entries, page=page,
                               has_next=len(rows) > page_size)

    @routes.get('/reports/storage')
    def storage_usage():
        owner = current_owner()
        if owner is None:
            abort(404)
        with engine.connect() as db:
            usage = _storage_usage(db, owner)
        return render_template('report_storage.html', usage=usage, display_bytes=_display_bytes)

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

    def require_csrf():
        tokens = request.form.getlist('csrf')
        expected = session.get('report_management_csrf')
        if (not expected or len(tokens) != 1 or not tokens[0].isascii()
                or not compare_digest(tokens[0], expected)):
            abort(403)

    @routes.route('/reports/trash/empty', methods=['GET', 'POST'])
    def empty_trash():
        owner = current_owner()
        if owner is None:
            abort(404)
        signer = URLSafeTimedSerializer(app.secret_key, salt=f'empty-browser-trash-v1:{owner}')
        if request.method == 'GET':
            with engine.connect() as db:
                entries, digest = _trash_snapshot(db, owner)
            if not entries:
                return redirect(url_for('report_management.trash_index'), code=303)
            return render_template('report_empty_trash.html', count=len(entries),
                                   confirmation=signer.dumps(digest))

        require_csrf()
        tokens = request.form.getlist('confirmation')
        if len(tokens) != 1 or len(tokens[0]) > 256:
            abort(400, description='Open Empty trash to review the assessments first.')
        try:
            expected = signer.loads(tokens[0], max_age=900)
        except BadData:
            abort(400, description='This confirmation is invalid or expired. Open Empty trash again.')
        changed = 'Trash changed. Return to Trash and review the current assessments.'
        with transaction(engine) as db:
            _begin_management_write(db)
            entries, digest = _trash_snapshot(db, owner)
            if digest != expected:
                abort(409, description=changed)
            for kind, entry_id, _ in entries:
                if _lock_assessment(db, owner, kind.lower(), entry_id, group=True, begun=True) is None:
                    abort(409, description=changed)
            if _trash_snapshot(db, owner)[1] != expected:
                abort(409, description=changed)
            for kind, entry_id, _ in entries:
                kind = kind.lower()
                if _remove_trash(db, owner, kind, entry_id) is None:
                    abort(409, description=changed)
                purge_assessment(db, owner, kind, entry_id, insert)
        flash('Trash emptied. File cleanup is queued.', 'report-management')
        return redirect(url_for('report_management.trash_index'), code=303)

    @routes.route('/reports/manage/<kind>/<entry_id>/rename', methods=['GET', 'POST'])
    def rename(kind, entry_id):
        if kind == 'batch':
            parent, payload = browser_batches, browser_batches.c.manifest
        elif kind == 'report':
            parent, payload = browser_reports, browser_reports.c.overview
        else:
            abort(404)
        owner = current_owner()
        query = select(payload, assessment_display_name(parent)).where(
            parent.c.id == entry_id, parent.c.owner_digest == owner,
            assessment_is_active(parent),
        )
        if kind == 'report':
            query = query.where(parent.c.batch_id.is_(None))
        if request.method == 'GET':
            with engine.connect() as db:
                row = db.execute(query).first()
            if row is None:
                abort(404)
            data, name = row
            return render_template('report_rename.html', original=_assessment_name(kind, data),
                                   name=name or '', kind=kind, entry_id=entry_id)

        require_csrf()
        names = request.form.getlist('display_name')
        if len(names) != 1:
            abort(400)
        name = names[0].strip()
        if len(name) > 80 or not all(char.isprintable() for char in name):
            abort(400, description='Display name must be at most 80 printable characters.')
        labels = browser_assessment_labels
        with transaction(engine) as db:
            assessment_id = _lock_assessment(db, owner, kind, entry_id)
            if assessment_id is None or db.execute(query).first() is None:
                abort(404)
            if name:
                db.execute(insert(labels).values(
                    owner_digest=owner, assessment_kind=kind.upper(),
                    assessment_id=assessment_id, display_name=name,
                ).on_conflict_do_update(index_elements=list(labels.primary_key.columns),
                                        set_={'display_name': name}))
            else:
                db.execute(labels.delete().where(
                    labels.c.owner_digest == owner, labels.c.assessment_kind == kind.upper(),
                    labels.c.assessment_id == assessment_id,
                ))
        flash('Display name updated.', 'report-management')
        return redirect(url_for('report_index'), code=303)

    @routes.post('/reports/manage/trash-selected')
    def trash_selected():
        require_csrf()
        entries = request.form.getlist('entry')
        if not 1 <= len(entries) <= 40:
            abort(400, description='Select between 1 and 40 assessments.')
        if not all(re.fullmatch(
                r'(batch:[a-f0-9]{32}|report:[a-f0-9]{32}\.[a-f0-9]{32})', entry)
                for entry in entries):
            abort(400, description='Invalid assessment selection.')
        owner = current_owner()
        if owner is None:
            abort(404)
        trash = browser_assessment_trash
        reports = browser_reports.c
        identity = func.coalesce(reports.assessment_group_id, reports.id)
        with transaction(engine) as db:
            _begin_management_write(db)
            targets = set()
            for entry in set(entries):
                kind, entry_id = entry.split(':', 1)
                if kind == 'report':
                    entry_id = db.scalar(select(identity).where(
                        reports.id == entry_id, reports.owner_digest == owner,
                        reports.batch_id.is_(None),
                    ))
                    if entry_id is None:
                        abort(404)
                targets.add((kind, entry_id))
            # Acquire the same group locks as individual actions, in a stable order.
            for kind, entry_id in sorted(targets):
                if _lock_assessment(db, owner, kind, entry_id, group=True, begun=True) is None:
                    abort(404)
            now = datetime.now(timezone.utc)
            db.execute(insert(trash).on_conflict_do_nothing(
                index_elements=list(trash.primary_key.columns)), [
                dict(owner_digest=owner, assessment_kind=kind.upper(), assessment_id=entry_id,
                     deleted_at=now, purge_after=now + retention)
                for kind, entry_id in sorted(targets)
            ])
        flash('Selected assessments moved to trash.', 'report-management')
        return redirect(url_for('report_index'), code=303)

    @routes.post('/reports/manage/<kind>/<entry_id>/<action>')
    def update_trash(kind, entry_id, action):
        if kind not in {'report', 'batch'} or action not in {'trash', 'restore', 'purge'}:
            abort(404)
        require_csrf()
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
