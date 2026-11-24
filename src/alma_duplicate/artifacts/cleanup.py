"""Reclaim explicitly queued local artifacts with no remaining references."""
from datetime import datetime, timezone

import click
from sqlalchemy import select

from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.models import (
    artifacts, assessment_input_snapshots, browser_artifact_cleanup, browser_reports,
)


def drain_browser_artifact_cleanup(engine, store, limit):
    """Process one bounded batch. Referenced files and failures stay queued."""
    queue = browser_artifact_cleanup
    with transaction(engine) as db:
        jobs = db.execute(select(queue.c.storage_key, queue.c.kind).order_by(
            queue.c.last_attempt_at.asc().nulls_first(), queue.c.created_at, queue.c.storage_key,
        ).limit(limit).with_for_update(skip_locked=True)).all()
        if not jobs:
            return 0, 0, 0
        candidates = {job.storage_key for job in jobs}
        kept = set(db.scalars(select(artifacts.c.storage_key).where(
            artifacts.c.storage_key.in_(candidates))))
        # Artifact paths are immutable and publication always allocates new
        # paths. Include every owner and trashed records in the reference scan.
        for manifest in db.scalars(select(browser_reports.c.artifact_manifest)).yield_per(256):
            kept.update(item['storage_key'] for item in manifest if item['storage_key'] in candidates)
        for upload in db.scalars(select(assessment_input_snapshots.c.upload).where(
                assessment_input_snapshots.c.upload.is_not(None))).yield_per(256):
            if upload is not None and upload['artifact']['storage_key'] in candidates:
                kept.add(upload['artifact']['storage_key'])

        count = failed = 0
        now = datetime.now(timezone.utc)
        for storage_key, kind in jobs:
            predicate = queue.c.storage_key == storage_key
            if storage_key not in kept:
                try:
                    store.remove(kind, storage_key)
                except (OSError, ValueError):
                    failed += 1
                else:
                    db.execute(queue.delete().where(predicate))
                    count += 1
                    continue
            db.execute(queue.update().where(predicate).values(last_attempt_at=now))
    return count, len(kept), failed


def register_browser_artifact_cleanup(app, engine, store):
    @app.cli.command('cleanup-browser-artifacts')
    @click.option('--limit', type=click.IntRange(1, 500), default=100, show_default=True)
    def cleanup_browser_artifacts(limit):
        """Process queued files whose database references have been removed."""
        removed, referenced, failed = drain_browser_artifact_cleanup(engine, store, limit)
        click.echo(f'Removed {removed}. Still referenced {referenced}. Failed {failed}.')
        if failed:
            raise click.ClickException('Failed files remain queued for retry.')
