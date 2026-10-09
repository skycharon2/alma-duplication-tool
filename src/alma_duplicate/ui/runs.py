"""Explicit browser source execution and temporary disk report retention."""

from dataclasses import dataclass

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation,
)
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.ui.run_store import RunStore as RunStore


@dataclass(frozen=True)
class BrowserAssessment:
    archive_replay: str | None = None
    queue_csv: str | None = None
    archive_array_evidence: str | None = None
    live_archive: bool = False
    live_aq: bool = False
    report_detail: str = 'matches'

    def __post_init__(self):
        if self.report_detail not in {'full', 'matches'}:
            raise ValueError('Report detail must be full or matches')
        if type(self.live_archive) is not bool:
            raise ValueError("LIVE_ARCHIVE must be boolean")
        if self.live_archive and self.archive_replay:
            raise ValueError(
                "Live Archive and Archive replay are mutually exclusive"
            )
        if type(self.live_aq) is not bool:
            raise ValueError("LIVE_AQ must be boolean")
        if self.live_aq and not self.live_archive:
            raise ValueError("Live AQ requires live Archive TAP")
        if self.live_aq and self.archive_array_evidence:
            raise ValueError("Live AQ and captured AQ evidence are mutually exclusive")

    @property
    def archive_kind(self):
        if self.live_archive:
            return "LIVE"
        if self.archive_replay:
            return "REPLAY"
        return None

    @property
    def enabled(self):
        return bool(self.archive_kind or self.queue_csv)

    def assess(self, document):
        """Construct fresh lazy providers; never fall back between Archive modes."""
        selected = document["search_options"]["sources"]
        intents = document["request"]["intents"]
        queue = "QUEUE" in selected
        archive_kind = self.archive_kind if "ARCHIVE" in selected else None

        def archive_provider():
            from alma_duplicate.archive_array_evidence import (
                load_archive_array_catalog,
            )

            catalog = (
                load_archive_array_catalog(self.archive_array_evidence)
                if self.archive_array_evidence
                else None
            )

            if archive_kind == "REPLAY":
                client = RecordedArchiveClient(self.archive_replay)
                return ArchiveInput(client, client.metadata, catalog)

            if archive_kind == "LIVE":
                from alma_duplicate.clients.archive_client import ArchiveClient

                return ArchiveInput(
                    ArchiveClient("https://almascience.eso.org/tap"),
                    array_catalog=catalog,
                )

            raise RuntimeError(
                "Archive provider requested without Archive configuration"
            )

        loader = (
            (lambda: QueueCsvClient().load(self.queue_csv))
            if self.queue_csv and queue
            else None
        )

        def fetch_archive_arrays(members):
            # The shared entry calls this only after TAP retained linked Members.
            from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
            return ArchiveAqClient().fetch_members(members)

        return assess_observation(
            document["request"],
            document["search_options"],
            report_detail=self.report_detail,
            options=AssessmentOptions(
                queue_common=queue,
                queue_continuum=queue and "CONTINUUM" in intents,
                queue_line=queue and "LINE" in intents,
            ),
            sources=AssessmentSources(
                archive_kind=archive_kind,
                archive_provider=archive_provider if archive_kind else None,
                queue_loader=loader,
                archive_array_fetcher=(
                    fetch_archive_arrays
                    if self.live_aq and archive_kind == "LIVE" else None
                ),
            ),
            # A browser form has no original input-file bytes to hash.
        )


# Historical internal name retained for import compatibility.
OfflineAssessment = BrowserAssessment
