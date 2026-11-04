"""Explicit browser source execution and temporary disk report retention."""

from dataclasses import dataclass, field, replace
from collections.abc import Callable

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation,
)
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.storage.queue_active import QueueActiveError
from alma_duplicate.ui.managed_queue import PinnedQueue, pin_active_queue
from alma_duplicate.ui.run_store import RunStore as RunStore
from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.reporting import json_value

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
    _pinned_queue: tuple[Callable | None, PinnedQueue | None] | None = field(
        default=None, repr=False, compare=False)

    def pin_queue_for_submission(self, selected):
        """Freeze source bytes or acquisition failure for every submitted branch."""
        if not selected or self._pinned_queue is not None:
            return self
        if self.managed_queue_root or not self.queue_csv:
            loader, selection = self._queue_input()
            from alma_duplicate.ui.queue_browser import memoized_loader
            return replace(self, _pinned_queue=(memoized_loader(loader), selection))
        from pathlib import Path
        try:
            raw = Path(self.queue_csv).read_bytes()
        except OSError as exc:
            message = f"could not read Queue CSV snapshot {self.queue_csv}: {exc}"

            def loader():
                raise OSError(message)
        else:
            # Parse once so every branch consumes the same pinned snapshot.
            def loader():
                return QueueCsvClient().parse_bytes(raw)
        from alma_duplicate.ui.queue_browser import memoized_loader
        return replace(self, _pinned_queue=(memoized_loader(loader), None))


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

    def _queue_input(self, selected=True):
        """Shared Single Pointing/Mosaic snapshot selection; never auto-download."""
        # Select and freeze Queue bytes now, before Archive/search work can
        # overlap with a later administrator activation of another snapshot.
        if not selected:
            return None, None
        if self._pinned_queue is not None:
            return self._pinned_queue
        selection = None
        if selected and self.managed_queue_root:
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
                      if self.queue_csv and selected else None)

        return loader, selection

    def assess_queue_custom(self, document, proposed):
        """Use the same configured CSV/approved snapshot as Single Pointing."""
        loader, selection = self._queue_input()
        from alma_duplicate.ui.queue_browser import assess_geometry
        result = assess_geometry(document, loader, proposed)
        if selection is not None and result.document is not None:
            result.document['sources']['QUEUE']['managed_snapshot'] = dict(selection.provenance)
        return result

    def assess_mosaic(self, document, proposed):
        """Run metadata-only Mosaic science; temporary acquisition files are scoped to this call."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from alma_duplicate.mosaic_backend import MosaicAssessmentInput
        from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient
        if not self.live_archive:
            raise ValueError("Browser Mosaic assessment requires live Archive configuration.")
        with TemporaryDirectory(prefix="alma-mosaic-") as directory:
            from alma_duplicate.separated_setup_input import SEPARATED_INPUT_CONTRACT
            if document['request'].get('line_input_contract') in {SEPARATED_INPUT_CONTRACT, 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'}:
                from types import SimpleNamespace
                from alma_duplicate.submitted_line_assessment import assess_submitted_line_mosaic_search_v2
                report = assess_submitted_line_mosaic_search_v2(
                    document['request'], MosaicAssessmentInput(
                        proposed, Path(directory) / 'assessment', None, 1.0,
                        discovery_origins=ARCHIVE_CONNECTIONS[self.archive_connection]),
                    archive_client=MirroredArchiveClient(
                        origins=ARCHIVE_CONNECTIONS[self.archive_connection],
                        completeness_policy='STATUS_THEN_COUNT'))
                return SimpleNamespace(document=report, status=report['assessment_status'])
            return assess_observation(document["request"], document["search_options"],
                sources=AssessmentSources(archive_kind="LIVE", archive_provider=lambda: ArchiveInput(
                    MirroredArchiveClient(origins=ARCHIVE_CONNECTIONS[self.archive_connection],
                                          completeness_policy="STATUS_THEN_COUNT"))),
                mosaic=MosaicAssessmentInput(proposed=proposed,
                    output_directory=Path(directory) / "assessment", cache_directory=None,
                    margin_arcsec=1.0,
                    discovery_origins=ARCHIVE_CONNECTIONS[self.archive_connection]))

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

        loader, selection = self._queue_input(queue)
        from alma_duplicate.ui.queue_browser import memoized_loader
        loader = memoized_loader(loader)

        if document['request'].get('line_input_contract') in {
                'SEPARATE_REQUIREMENTS_AND_SPW_EVIDENCE_V1', 'SEPARATE_OBSERVATION_REQUIREMENTS_V2'}:
            from types import SimpleNamespace
            from alma_duplicate.submitted_line_assessment import assess_submitted_line_single_v2
            source = archive_provider() if archive_kind else None
            fetcher = None
            if self.live_aq and archive_kind == 'LIVE':
                from alma_duplicate.clients.archive_mirrors import MirroredArchiveAqClient
                fetcher = MirroredArchiveAqClient(origins=ARCHIVE_CONNECTIONS[self.archive_connection]).fetch_members
            report = assess_submitted_line_single_v2(document['request'], document['search_options'],
                archive_client=source.client if source else None, archive_arrays=source.array_catalog if source else None,
                archive_replay_metadata=source.replay_metadata if source else None, archive_array_fetcher=fetcher,
                queue_loader=loader, report_detail=self.report_detail)
            if selection is not None:
                report["sources"]["QUEUE"]["managed_snapshot"] = dict(selection.provenance)
            self._append_queue_geometry(document, report, loader, queue)
            return SimpleNamespace(document=report, status=report['assessment_status'])

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
        if assessment.document is not None:
            self._append_queue_geometry(document, assessment.document, loader, queue)
        return assessment

    def _append_queue_geometry(self, document, report, loader, selected):
        if not selected or document['request'].get('target_kind') != 'FIXED':
            return
        from alma_duplicate.ui.queue_browser import assess_geometry
        try:
            geometry = assess_geometry(document, loader)
            report['queue_geometry_assessment'] = json_value(geometry.document)
        except (OSError, ValueError) as exc:
            report['queue_geometry_assessment'] = {
                'assessment_status': 'SOURCES_UNAVAILABLE', 'geometry_reports': {},
                'search_completeness': 'NOT_ESTABLISHED',
                'error': str(exc),
            }


# Historical internal name retained for import compatibility.
OfflineAssessment = BrowserAssessment
