"""Local offline execution and bounded, process-local report retention."""

from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation,
)
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.reports import ReportArtifact, report_artifact


@dataclass(frozen=True)
class BrowserAssessment:
    archive_replay: str | None = None
    queue_csv: str | None = None
    archive_array_evidence: str | None = None

    @property
    def enabled(self):
        return bool(self.archive_replay or self.queue_csv)

    def assess(self, document):
        """Construct fresh lazy providers; never substitute a live Archive client."""
        selected = document["search_options"]["sources"]
        intents = document["request"]["intents"]
        queue = "QUEUE" in selected

        def archive_provider():
            client = RecordedArchiveClient(self.archive_replay)
            from alma_duplicate.archive_array_evidence import load_archive_array_catalog
            catalog = load_archive_array_catalog(self.archive_array_evidence) if self.archive_array_evidence else None
            return ArchiveInput(client, client.metadata, catalog)

        replay = self.archive_replay and "ARCHIVE" in selected
        loader = (lambda: QueueCsvClient().load(self.queue_csv)) if self.queue_csv and queue else None
        return assess_observation(
            document["request"], document["search_options"],
            options=AssessmentOptions(
                queue_common=queue,
                queue_continuum=queue and "CONTINUUM" in intents,
                queue_line=queue and "LINE" in intents,
            ),
            sources=AssessmentSources(
                archive_kind="REPLAY" if replay else None,
                archive_provider=archive_provider if replay else None,
                queue_loader=loader,
            ),
            # A browser form has no original input-file bytes to hash.
        )


# Historical internal name retained for import compatibility.
OfflineAssessment = BrowserAssessment

@dataclass(frozen=True)
class AssessmentRun:
    artifact: ReportArtifact
    request_bytes: bytes
    status: str

    @property
    def byte_size(self):
        return len(self.artifact.raw) + len(self.artifact.inspection_bytes) + len(self.request_bytes)


class RunStore:
    """Retain immutable exported bytes; bounded by count and serialized byte size.

    Local single-process UI only: IDs are references, not access control. Oldest
    runs are evicted first. Restarting the application clears the store.
    """

    def __init__(self, max_runs=20, max_bytes=32 * 1024 * 1024):
        if type(max_runs) is not int or max_runs < 1 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("Run retention limits must be positive integers")
        self._max_runs = max_runs
        self._max_bytes = max_bytes
        self._runs = OrderedDict()
        self._size = 0
        self._lock = Lock()

    def add(self, request_document, result):
        if result.document is None:
            raise ValueError("An assessment without a report cannot be retained")
        artifact = report_artifact(
            "Offline assessment", report_json_text(result.document).encode("utf-8"),
        )
        run = AssessmentRun(artifact, report_json_text(request_document).encode("utf-8"), str(result.status))
        if run.byte_size > self._max_bytes:
            raise ValueError("Report exceeds this application's in-memory retention limit")
        with self._lock:
            while self._runs and (len(self._runs) >= self._max_runs or self._size + run.byte_size > self._max_bytes):
                _, old = self._runs.popitem(last=False)
                self._size -= old.byte_size
            run_id = uuid4().hex
            self._runs[run_id] = run
            self._size += run.byte_size
        return run_id

    def get(self, run_id):
        with self._lock:
            return self._runs.get(run_id)
