"""Browser-owned trash transitions and visibility rules."""
from datetime import datetime, timedelta, timezone
import os
from secrets import compare_digest, token_hex

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.models import (
    browser_assessment_trash, browser_batches, browser_reports,
)


def assessment_is_active(parent):
    columns = parent.c
    if parent is browser_reports:
        kind = case((columns.batch_id.is_not(None), 'BATCH'), else_='REPORT')
        identity = func.coalesce(columns.batch_id, columns.assessment_group_id, columns.id)
    else:
        kind, identity = 'BATCH', columns.id
    trash = browser_assessment_trash.c
    return ~select(trash.assessment_id).where(
        trash.owner_digest == columns.owner_digest,
        trash.assessment_kind == kind,
        trash.assessment_id == identity,
    ).correlate(parent).exists()


def register_report_management(app, engine, current_owner):
    days = app.config.get('REPORT_TRASH_RETENTION_DAYS')
    if days is None:
        days = int(os.environ.get('ALMA_REPORT_TRASH_RETENTION_DAYS', '7'))
    if type(days) is not int or days < 1:
        raise ValueError('REPORT_TRASH_RETENTION_DAYS must be a positive integer')
    retention = timedelta(days=days)
    routes = Blueprint('report_management', __name__)

    @app.context_processor
    def trash_token():
        if request.endpoint not in {'report_index', 'report_management.trash_index'}:
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
                trash.c.deleted_at, report.c.id, report.c.overview, batch.c.id, batch.c.manifest,
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
        for deleted_at, report_id, overview, batch_id, manifest in rows[:page_size]:
            if manifest is not None:
                name = f"Multi-source assessment · {len(manifest['sources'])} targets"
                kind, entry_id = 'batch', batch_id
            else:
                name = overview['listing']['target']
                kind, entry_id = 'report', report_id
            entries.append(dict(name=name, kind=kind, id=entry_id, deleted_at=deleted_at))
        return render_template('report_trash.html', entries=entries, page=page,
                               has_next=len(rows) > page_size)

    @routes.post('/reports/manage/<kind>/<entry_id>/<action>')
    def update_trash(kind, entry_id, action):
        if kind not in {'report', 'batch'} or action not in {'trash', 'restore'}:
            abort(404)
        tokens = request.form.getlist('csrf')
        expected = session.get('report_management_csrf')
        if (not expected or len(tokens) != 1 or not tokens[0].isascii()
                or not compare_digest(tokens[0], expected)):
            abort(403)
        owner = current_owner()
        if owner is None:
            abort(404)

        if kind == 'batch':
            columns = browser_batches.c
            target = select(columns.id)
        else:
            columns = browser_reports.c
            target = select(func.coalesce(columns.assessment_group_id, columns.id)).where(
                columns.batch_id.is_(None))
        trash = browser_assessment_trash
        with transaction(engine) as db:
            assessment_id = db.scalar(target.where(
                columns.id == entry_id, columns.owner_digest == owner))
            if assessment_id is None:
                abort(404)
            key = dict(owner_digest=owner, assessment_kind=kind.upper(), assessment_id=assessment_id)
            if action == 'trash':
                now = datetime.now(timezone.utc)
                insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
                db.execute(insert(trash).values(
                    **key, deleted_at=now, purge_after=now + retention,
                ).on_conflict_do_nothing(index_elements=list(trash.primary_key.columns)))
            else:
                db.execute(trash.delete().where(
                    trash.c.owner_digest == owner, trash.c.assessment_kind == kind.upper(),
                    trash.c.assessment_id == assessment_id,
                ))
        if action == 'trash':
            flash('Assessment moved to trash.', 'report-management')
            return redirect(url_for('report_index'), code=303)
        flash('Assessment restored to Existing reports.', 'report-management')
        return redirect(url_for('report_management.trash_index'), code=303)

    app.register_blueprint(routes)
