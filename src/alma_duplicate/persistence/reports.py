"""Publish existing report artifacts and reopen them without scientific execution."""
import json
from uuid import uuid4

from sqlalchemy import select
from alma_duplicate.artifacts.base import Artifact, FILES
from alma_duplicate.persistence import models as m
from alma_duplicate.persistence.db import transaction
from alma_duplicate.persistence.repositories import WorkspaceRepository, RecordUnavailable

REQUIRED = {'report', 'request', 'inspection', 'view'}


def publish_report(engine, store, workspace_id, job_id, *, attempt, lease_token,
                   request_document, result, source_provenance, max_bytes=1024**3):
    """Persist files first, then atomically register a complete job result.

    Database failures leave unreferenced bundles for future reconciliation. Never
    delete a bundle on a commit exception: the commit outcome may be uncertain.
    """
    from alma_duplicate.ui.run_store import RunStore
    with_store = RunStore(max_bytes=max_bytes)
    try:
        temporary_id = with_store.add(request_document, result)
        directory = with_store.directory / temporary_id
        artifacts = store.put_bundle({kind: directory / name for kind, name in FILES.items()
                                      if (directory / name).is_file()})
    finally:
        with_store.close()
    if not REQUIRED <= {a.kind for a in artifacts}:
        raise ValueError('Required report artifacts missing')
    with transaction(engine) as session:
        repo = WorkspaceRepository(session, workspace_id)
        run_id = repo.record_run(job_id, attempt=attempt, lease_token=lease_token,
            report_schema=str(result.document.get('schema_version') or
                              'report_' + str(result.document['report_version'])), assessment_status=str(result.status),
            source_provenance=source_provenance)
        for artifact in artifacts:
            session.execute(m.artifacts.insert().values(id=uuid4().hex, workspace_id=workspace_id,
                run_id=run_id, kind=artifact.kind, storage_key=artifact.storage_key,
                sha256=artifact.sha256, byte_size=artifact.byte_size))
        session.execute(m.jobs.update().where(m.jobs.c.id == job_id,
            m.jobs.c.workspace_id == workspace_id).values(state='COMPLETED',
            lease_token=None, lease_expires_at=None, heartbeat_at=None))
    return run_id


class SavedReport:
    """Workspace-scoped saved artifacts. Caller supplies an authorized workspace."""
    def __init__(self, engine, store, workspace_id, run_id):
        self.store = store
        with transaction(engine) as session:
            repo = WorkspaceRepository(session, workspace_id)
            self.run = repo.get_run(run_id)
            job = repo.get_job(self.run['job_id'])
            if job['state'] != 'COMPLETED' or job['attempt'] != self.run['attempt']:
                raise RecordUnavailable('Report unavailable')
            rows = session.execute(select(m.artifacts).where(
                m.artifacts.c.workspace_id == workspace_id, m.artifacts.c.run_id == run_id)).mappings()
            self.artifacts = {r['kind']: Artifact(r['kind'], r['storage_key'], r['sha256'], r['byte_size'])
                              for r in rows}
        if not REQUIRED <= self.artifacts.keys():
            raise RecordUnavailable('Report unavailable')

    def open_download(self, kind):
        if kind not in {'report', 'request', 'inspection'}:
            raise ValueError('Unknown download kind')
        return self.store.open_verified(self.artifacts[kind])

    def _json(self, kind):
        with self.store.open_verified(self.artifacts[kind]) as stream:
            return json.load(stream)

    def document(self):
        """Read the saved scientific document for existing visualization adapters."""
        return self._json('report')

    def page(self, page=1, view='matches'):
        from alma_duplicate.ui.report_pages import report_page
        from alma_duplicate.ui.mosaic_report_pages import mosaic_report_page
        from alma_duplicate.ui.queue_custom_report import report_page as custom_page
        projection = self._json('view')
        if projection.get('unified_queue'):
            return self.queue_page(page, view)
        reader = (custom_page if projection.get('queue_custom') else
                  mosaic_report_page if projection.get('mosaic') else report_page)
        with self.store.open_verified(self.artifacts['report']) as stream:
            def context(index):
                offset, length = projection['offsets'][index]
                stream.seek(offset)
                return json.loads(stream.read(length))
            data = reader(projection, page, view, context)
        if 'queue_index' in projection:
            data['document']['queue_geometry_assessment'] = self.queue_page()['document']
        data.update(persistent=True, run_id=self.run['id'], run=dict(self.run, status=self.run['assessment_status']))
        return data

    def queue_page(self, page=1, view='matches'):
        from alma_duplicate.ui.queue_saved_pages import queue_saved_page
        projection = self._json('view')
        if 'queue_index' not in projection:
            return None
        with self.store.open_verified(self.artifacts['queue-candidates']) as stream:
            def candidate(entry):
                stream.seek(entry['offset'])
                return json.loads(stream.read(entry['length']))
            data = queue_saved_page(projection, page, view, candidate)
        data.update(persistent=True, run_id=self.run['id'],
                    run=dict(self.run, status=self.run['assessment_status']))
        return data
