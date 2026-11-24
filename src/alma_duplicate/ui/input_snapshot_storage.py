"""Persistence for browser-owned input snapshots and immutable uploads."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sqlalchemy import select
from werkzeug.utils import secure_filename

from alma_duplicate.artifacts.base import Artifact
from alma_duplicate.parsers.ot_pointings import MAX_BYTES as OT_MAX_BYTES
from alma_duplicate.parsers.source_list import MAX_BYTES as SOURCE_MAX_BYTES
from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.models import (
    assessment_input_links as links, assessment_input_snapshots as snapshots, browser_reports,
)
from alma_duplicate.ui.input_snapshot import restore_input_snapshot
from alma_duplicate.ui.report_management import assessment_is_active

_UPLOADS = {
    'MULTI_SOURCE_SINGLE': ('source-list', SOURCE_MAX_BYTES, {'csv', 'txt'}),
    'MOSAIC': ('ot-pointings', OT_MAX_BYTES, {'ot'}),
}


def insert_input_snapshot(db, store, owner, snapshot, upload):
    """Bind a snapshot and verified file descriptor in the caller's transaction."""
    restore_input_snapshot(snapshot)
    evidence = None
    expected = _UPLOADS.get(snapshot['workflow'])
    if expected:
        kind, limit, formats = expected
        if not upload or upload.get('format') not in formats:
            raise ValueError('Assessment input upload is unavailable')
        raw = upload.get('raw')
        if (not isinstance(raw, bytes) or not 0 < len(raw) <= limit
                or sha256(raw).hexdigest() != upload.get('input_sha256')):
            raise ValueError('Assessment input upload does not match its preview')
        filename = secure_filename(upload.get('filename') or '')[:200] or kind
        with TemporaryDirectory(prefix='alma-input-') as directory:
            path = Path(directory) / 'upload'
            path.write_bytes(raw)
            artifact, = store.put_bundle({kind: path})
        evidence = dict(artifact=asdict(artifact), filename=filename, format=upload['format'])
    elif upload is not None:
        raise ValueError('Unexpected upload for this assessment snapshot')
    snapshot_id = uuid4().hex
    db.execute(snapshots.insert().values(id=snapshot_id, owner_digest=owner,
                                        snapshot=snapshot, upload=evidence))
    return snapshot_id


def read_input_snapshot(engine, store, owner, parent, parent_id):
    """Look up through the owning report or batch and verify any stored upload."""
    if owner is None:
        return None
    link = links.c.report_id if parent is browser_reports else links.c.batch_id
    with transaction(engine) as db:
        row = db.execute(select(snapshots.c.id, snapshots.c.snapshot, snapshots.c.upload)
            .join(links, links.c.snapshot_id == snapshots.c.id)
            .join(parent, parent.c.id == link)
            .where(parent.c.id == parent_id, parent.c.owner_digest == owner,
                   snapshots.c.owner_digest == owner,
                   assessment_is_active(parent))).mappings().first()
    if row is None:
        return None
    snapshot = row['snapshot']
    restore_input_snapshot(snapshot)
    expected = _UPLOADS.get(snapshot['workflow'])
    upload = row['upload']
    if expected:
        kind, limit, formats = expected
        if upload is None or upload['format'] not in formats:
            raise ValueError('Saved assessment input upload is unavailable')
        artifact = Artifact(**upload['artifact'])
        if artifact.kind != kind or not 0 < artifact.byte_size <= limit:
            raise ValueError('Invalid saved assessment input upload')
        with store.open_verified(artifact) as stream:
            raw = stream.read(limit + 1)
        if len(raw) != artifact.byte_size:
            raise ValueError('Invalid saved assessment input upload size')
        upload = dict(filename=upload['filename'], format=upload['format'],
                      raw=raw, input_sha256=artifact.sha256)
    elif upload is not None:
        raise ValueError('Unexpected saved assessment input upload')
    return dict(snapshot_id=row['id'], snapshot=snapshot, upload=upload)
