"""Explicit browser source execution and temporary disk report retention."""

from dataclasses import dataclass

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation,
)
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.storage.queue_active import QueueActiveError
from alma_duplicate.ui.managed_queue import pin_active_queue
from alma_duplicate.ui.run_store import RunStore as RunStore
from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS

ARCHIVE_CONNECTIONS = {
    "AUTO": ARCHIVE_ORIGINS,
    "EUROPE": (ARCHIVE_ORIGINS[0],),
    "EAST_ASIA": (ARCHIVE_ORIGINS[1],),
    "NORTH_AMERICA": (ARCHIVE_ORIGINS[2],),
}


@dataclass(frozen=True)
class BrowserAssessment:
    archive_replay: str | None = None
    queue_csv: str | None = None
    archive_array_evidence: str | None = None
    live_archive: bool = False
    live_aq: bool = False
    report_detail: str = 'matches'
    managed_queue_root: str | None = None
    archive_connection: str = "AUTO"

    def __post_init__(self):
        if self.archive_connection not in ARCHIVE_CONNECTIONS:
            raise ValueError("Invalid Archive connection selection")
        if self.queue_csv and self.managed_queue_root:
            raise ValueError("manual Queue CSV and managed Queue root are mutually exclusive")
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
        return bool(self.archive_kind or self.queue_csv or self.managed_queue_root)

    def assess_mosaic(self, document, proposed):
        """Run metadata-only Mosaic science; temporary acquisition files are scoped to this call."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from alma_duplicate.mosaic_backend import MosaicAssessmentInput
        from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient
        if not self.live_archive:
            raise ValueError("Browser Mosaic assessment requires live Archive configuration.")
        with TemporaryDirectory(prefix="alma-mosaic-") as directory:
            return assess_observation(document["request"], document["search_options"],
                sources=AssessmentSources(archive_kind="LIVE", archive_provider=lambda: ArchiveInput(
                    MirroredArchiveClient(origins=ARCHIVE_CONNECTIONS[self.archive_connection],
                                          completeness_policy="STATUS_THEN_COUNT"))),
                mosaic=MosaicAssessmentInput(proposed=proposed,
                    output_directory=Path(directory) / "assessment", cache_directory=None,
                    margin_arcsec=1.0,
                    discovery_origin=ARCHIVE_CONNECTIONS[self.archive_connection][0]))

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
                from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient

                return ArchiveInput(
                    MirroredArchiveClient(origins=ARCHIVE_CONNECTIONS[self.archive_connection],
                                          completeness_policy="STATUS_THEN_COUNT"),
                    array_catalog=catalog,
                )

            raise RuntimeError(
                "Archive provider requested without Archive configuration"
            )

        # Select and freeze Queue bytes now, before Archive/search work can
        # overlap with a later administrator activation of another snapshot.
        selection = None
        if queue and self.managed_queue_root:
            try:
                selection = pin_active_queue(self.managed_queue_root)
            except (QueueActiveError, OSError) as exc:
                message = f"{type(exc).__name__}: {exc}"

                def unavailable_queue():
                    raise QueueActiveError(message)

                loader = unavailable_queue  # Shared entry reports Queue FAILED, not empty.
            else:
                loader = selection.parse
        else:
            loader = ((lambda: QueueCsvClient().load(self.queue_csv))
                      if self.queue_csv and queue else None)

        def fetch_archive_arrays(members):
            # The shared entry calls this only after TAP retained linked Members.
            from alma_duplicate.clients.archive_mirrors import MirroredArchiveAqClient
            return MirroredArchiveAqClient(origins=ARCHIVE_CONNECTIONS[self.archive_connection]).fetch_members(members)

        assessment = assess_observation(
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
        if selection is not None and assessment.document is not None:
            # Add an optional browser-specific evidence binding without changing
            # report version, evaluated science or archive-only reports.
            queue_report = assessment.document.get("sources", {}).get("QUEUE")
            if queue_report is not None:
                queue_report["managed_snapshot"] = dict(selection.provenance)
        return assessment


# Historical internal name retained for import compatibility.
OfflineAssessment = BrowserAssessment
