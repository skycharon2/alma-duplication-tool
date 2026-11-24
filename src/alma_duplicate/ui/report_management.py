"""Browser-owned trash transitions and visibility rules."""
from datetime import datetime, timedelta, timezone
import os
from secrets import compare_digest, token_hex

from flask import Blueprint, abort, redirect, request, session, url_for
from sqlalchemy import case, func, select
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
        if request.endpoint != 'report_index':
            return {}
        return {'report_management_csrf': session.setdefault('report_management_csrf', token_hex(32))}

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
        return redirect(url_for('report_index'), code=303)

    app.register_blueprint(routes)
