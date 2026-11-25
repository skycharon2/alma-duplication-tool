"""Saved reports survive reopen and never trigger source acquisition."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from sqlalchemy import create_engine, select, func
from alembic import command
from alma_duplicate.artifacts.local import LocalArtifactStore
from alma_duplicate.persistence import models as m
from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.reports import publish_report, SavedReport
from alma_duplicate.persistence.repositories import RecordUnavailable, StaleAttempt
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.visualization import visualization_data
from tests.persistence.test_foundation import connection as connection_fixture, seed, config
from tests.ui.test_run_store import assessment as assessment_fixture

connection = connection_fixture
assessment = assessment_fixture


def prepare(conn):
    seed(conn)
    now = datetime.now(timezone.utc)
    with transaction(conn) as session:
        session.execute(m.jobs.insert().values(id='job', workspace_id='a', submission_id='s',
            source_id='src', purpose='LINE', state='RUNNING', attempt=1, lease_token='lease',
            heartbeat_at=now, lease_expires_at=now+timedelta(hours=1)))


def publish(conn, store, assessment, token='lease'):
    request, result = assessment
    return publish_report(conn, store, 'a', 'job', attempt=1, lease_token=token,
                          request_document=request, result=result, source_provenance={})


def test_reopen_scoping_hash_and_presentation(connection, tmp_path, assessment, monkeypatch):
    prepare(connection)
    root = tmp_path / 'artifacts'
    identity = publish(connection, LocalArtifactStore(root), assessment)
    from alma_duplicate.ui.runs import BrowserAssessment
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Recomputed saved report'))
    saved = SavedReport(connection, LocalArtifactStore(root), 'a', identity)
    assert saved.page()['persistent']
    assert visualization_data(saved.page())
    with saved.open_download('report') as stream:
        assert stream.read() == report_json_text(assessment[1].document).encode()
    with pytest.raises(RecordUnavailable):
        SavedReport(connection, LocalArtifactStore(root), 'b', identity)
    artifact = saved.artifacts['report']
    path = root / artifact.storage_key
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='mismatch'):
        saved.page()


def test_failed_database_publication_leaves_no_visible_run(connection, tmp_path, assessment):
    prepare(connection)
    store = LocalArtifactStore(tmp_path / 'artifacts')
    with pytest.raises(StaleAttempt):
        publish(connection, store, assessment, token='stale')
    with transaction(connection) as session:
        assert session.scalar(select(func.count()).select_from(m.runs)) == 0
        assert session.scalar(select(func.count()).select_from(m.artifacts)) == 0
        assert session.scalar(select(m.jobs.c.state)) == 'RUNNING'
    assert len(list(store.root.iterdir())) == 1  # unreferenced immutable bundle
    assert not list(store.root.glob('.pending-*'))


def test_paths_symlinks_and_interrupted_copy(tmp_path):
    store = LocalArtifactStore(tmp_path / 'artifacts')
    source = tmp_path / 'input'
    source.write_bytes(b'original')
    artifact = store.put_bundle({'report': source})[0]
    with pytest.raises(ValueError):
        store.open_verified(replace(artifact, storage_key='../input'))
    path = store.root / artifact.storage_key
    path.unlink()
    path.symlink_to(source)
    with pytest.raises(OSError):
        store.open_verified(artifact)
    with pytest.raises(ValueError):
        store.remove(artifact.kind, '../input')
    store.remove(artifact.kind, artifact.storage_key)
    store.remove(artifact.kind, artifact.storage_key)
    assert source.read_bytes() == b'original'
    path.parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        store.remove(artifact.kind, artifact.storage_key)
    with pytest.raises(FileNotFoundError):
        store.put_bundle({'report': source, 'request': tmp_path / 'missing'})
    assert not list(store.root.glob('.pending-*'))


def test_browser_inspection_compression_keeps_download_bytes(tmp_path):
    source = tmp_path / 'inspection.json'
    raw = b'[' + b'{"evidence":"stable"},' * 10000 + b'{}]'
    source.write_bytes(raw)
    root = tmp_path / 'artifacts'
    legacy, = LocalArtifactStore(root).put_bundle({'inspection': source})
    compressed, = LocalArtifactStore(root, compress_inspection=True).put_bundle({'inspection': source})
    assert compressed.storage_key.endswith('/inspection.json.gz')
    assert compressed.stored_byte_size == (root / compressed.storage_key).stat().st_size
    assert compressed.stored_byte_size < len(raw) // 10
    assert compressed.byte_size == legacy.byte_size and compressed.sha256 == legacy.sha256
    reader = LocalArtifactStore(root)
    for artifact in (legacy, compressed):
        with reader.open_verified(artifact) as stream:
            assert stream.read() == raw
        reader.remove(artifact.kind, artifact.storage_key)
        assert not (root / artifact.storage_key).exists()


def test_new_process_can_read_saved_report(tmp_path, assessment):
    database = tmp_path / 'metadata.sqlite'
    url = 'sqlite:///' + str(database)
    engine = create_engine(url)
    with engine.connect() as conn:
        command.upgrade(config(conn), 'head')
        conn.commit()
        prepare(conn)
    root = tmp_path / 'artifacts'
    identity = publish(engine, LocalArtifactStore(root), assessment)
    engine.dispose()
    script = '''
import json, sys
from sqlalchemy import create_engine
from alma_duplicate.artifacts.local import LocalArtifactStore
from alma_duplicate.persistence.reports import SavedReport
from alma_duplicate.ui.runs import BrowserAssessment
from alma_duplicate.ui.visualization import visualization_data
BrowserAssessment.assess = lambda *a: (_ for _ in ()).throw(RuntimeError('forbidden'))
engine = create_engine(sys.argv[1])
saved = SavedReport(engine, LocalArtifactStore(sys.argv[2]), 'a', sys.argv[3])
assert visualization_data(saved.page())
with saved.open_download('report') as stream:
    document = json.load(stream)
print(json.dumps({'version': document['report_version'], 'persistent': saved.page()['persistent']}))
engine.dispose()
'''
    result = subprocess.run([sys.executable, '-c', script, url, str(root), identity],
                            check=True, capture_output=True, text=True,
                            cwd=Path(__file__).parents[2])
    assert json.loads(result.stdout)['persistent'] is True


def test_flask_restarts_keep_existing_urls_and_require_resolver(connection, tmp_path, assessment, monkeypatch):
    from alma_duplicate.ui import create_app
    from alma_duplicate.ui.runs import BrowserAssessment
    from tests.ui.test_runs import config as ui_config
    prepare(connection)
    root = tmp_path / 'artifacts'
    identity = publish(connection, LocalArtifactStore(root), assessment)
    monkeypatch.setattr(BrowserAssessment, 'assess', lambda *a: pytest.fail('Recomputed saved report'))
    for workspace in ['a', 'a', 'b', None]:
        app = create_app(ui_config())
        if workspace is not None:
            app.extensions['persistent_report_resolver'] = lambda key: SavedReport(
                connection, LocalArtifactStore(root), workspace, key)
        try:
            client = app.test_client()
            expected = 200 if workspace == 'a' else 404
            for suffix in ['', '/visualization', '/download/report']:
                response = client.get('/runs/' + identity + suffix)
                assert response.status_code == expected
                response.close()
            if workspace == 'a':
                assert b'read from persistent storage' in client.get('/runs/' + identity).data
        finally:
            app.extensions['assessment_runs'].close()
            app.extensions['source_uploads'].close()
            app.extensions['mosaic_uploads'].close()


def test_failed_index_insert_rolls_back_run_and_job(connection, tmp_path, assessment):
    from sqlalchemy.exc import IntegrityError
    prepare(connection)
    class DuplicateIndexStore(LocalArtifactStore):
        def put_bundle(self, files):
            records = super().put_bundle(files)
            return records + [records[0]]
    with pytest.raises(IntegrityError):
        publish(connection, DuplicateIndexStore(tmp_path / 'artifacts'), assessment)
    with transaction(connection) as session:
        assert session.scalar(select(func.count()).select_from(m.runs)) == 0
        assert session.scalar(select(func.count()).select_from(m.artifacts)) == 0
        assert session.scalar(select(m.jobs.c.state)) == 'RUNNING'


def test_same_size_tampering_is_detected(tmp_path):
    store = LocalArtifactStore(tmp_path / 'artifacts')
    source = tmp_path / 'input'
    source.write_bytes(b'original')
    artifact = store.put_bundle({'report': source})[0]
    (store.root / artifact.storage_key).write_bytes(b'modified')
    with pytest.raises(ValueError, match='digest mismatch'):
        store.open_verified(artifact)
