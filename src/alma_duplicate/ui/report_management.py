"""Visibility rules shared by browser report history, downloads and reuse."""
from sqlalchemy import case, func, select

from alma_duplicate.persistence.models import browser_assessment_trash, browser_reports


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
