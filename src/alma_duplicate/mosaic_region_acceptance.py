"""Bounded live acceptance and exact offline replay of metadata-only Mosaic runs."""

from hashlib import sha256
import io
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from astropy.io.votable import parse
from pyvo.dal import TAPResults

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.archive_mosaic_discovery import _fetch
from alma_duplicate.archive_mosaic_pipeline import MAX_METADATA_BYTES
from alma_duplicate.assessment import (
    assess_observation,
    AssessmentSources,
    ArchiveInput,
)
from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.mosaic_candidate_discovery import discover_candidates


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


class CaptureService:
    def __init__(self, folder, endpoint):
        self.folder, self.endpoint, self.responses = folder, endpoint, []

    def run_sync(self, query, *, maxrec):
        url = (
            self.endpoint
            + "/sync?"
            + urlencode(
                dict(
                    REQUEST="doQuery",
                    LANG="ADQL",
                    FORMAT="votable",
                    QUERY=query,
                    MAXREC=maxrec,
                )
            )
        )
        code, raw = _fetch(url)
        name = f"response-{len(self.responses):03d}.xml"
        (self.folder / name).write_bytes(raw)
        self.responses.append(
            dict(
                adql=query,
                maxrec=maxrec,
                file=name,
                sha256=sha256(raw).hexdigest(),
                http_status=code,
            )
        )
        if code != 200:
            raise ValueError(f"TAP HTTP {code}")
        if len(raw) > MAX_METADATA_BYTES:
            raise ValueError("TAP response exceeds capture byte limit")
        return TAPResults(parse(io.BytesIO(raw)))


class MetadataBundleClient:
    """One exact-query manifest per candidate; replay never opens a network."""

    def __init__(self, root, *, live=False):
        self.root, self.live = Path(root), live
        self.request_count = 0

    def search(self, spec):
        key = sha256(
            json.dumps([spec.member_ous_uid, spec.target_name]).encode()
        ).hexdigest()
        folder = self.root / key
        manifest = folder / "manifest.json"
        if not self.live:
            return RecordedArchiveClient(manifest).search(spec)
        folder.mkdir(parents=True, exist_ok=False)
        endpoint = ARCHIVE_ORIGINS[0] + "/tap"
        service = CaptureService(folder, endpoint)
        result = ArchiveClient(
            endpoint, executor=PyvoTapExecutor(endpoint, service=service)
        ).search(spec)
        self.request_count += len(service.responses)
        p = result.provenance
        write_json(
            manifest,
            dict(
                replay_version="1",
                fixture_kind="CAPTURED_TAP_RESPONSE",
                endpoint=endpoint,
                maxrec=p.configured_maxrec,
                query_run_id=p.query_run_id,
                started_at=p.started_at.isoformat(),
                finished_at=p.finished_at.isoformat(),
                responses=service.responses,
                expected_count=p.expected_count,
                retrieved_count=p.retrieved_count,
                status=result.status.value,
            ),
        )
        return result


def seal(root):
    files = {
        str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "bundle.json"
    }
    write_json(
        root / "bundle.json",
        dict(schema_version="mosaic_region_capture_1", files=files),
    )


def verify(root):
    manifest = json.loads((root / "bundle.json").read_text())
    if manifest.get("schema_version") != "mosaic_region_capture_1":
        raise ValueError("Unsupported region capture bundle")
    for name, digest in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Invalid capture path")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Capture checksum mismatch: {name}")
    required = {"request.json", "proposed.json", "selection/discovery.json"}
    if not required.issubset(manifest["files"]):
        raise ValueError("Capture is missing required inputs")
    # Every file that replay could consume must be covered by the checksum index.
    actual = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p.name != "bundle.json"
    }
    if actual != set(manifest["files"]):
        raise ValueError("Capture contains unindexed files")


def run_acceptance(
    output, *, request=None, proposed=None, members=(), replay=None, margin_arcsec=1.0
):
    """Live selection is a declared engineering subset, never a full-search verdict."""
    started = time.monotonic()
    output = Path(output)
    if replay is not None:
        root = Path(replay)
        verify(root)
        if output.resolve().is_relative_to(root.resolve()):
            raise ValueError("Replay output must be outside the capture bundle")
        request = json.loads((root / "request.json").read_text())
        proposed = json.loads((root / "proposed.json").read_text())
        discovery = json.loads((root / "selection/discovery.json").read_text())
        margin_arcsec = discovery["plan"]["margin_arcsec"]
    else:
        if not 1 <= len(set(members)) <= 10:
            raise ValueError(
                "Select 1 to 10 explicit Member UIDs for bounded live acceptance"
            )
    output.mkdir(parents=True, exist_ok=False)
    if replay is None:
        root = output / "capture"
        root.mkdir()
        write_json(root / "request.json", request)
        write_json(root / "proposed.json", proposed)
        discovery = discover_candidates(
            proposed, root / "discovery", margin_arcsec=margin_arcsec
        )
        selected = [
            c for c in discovery["candidates"] if c["member_ous_uid"] in members
        ]
        if set(members) != {c["member_ous_uid"] for c in selected}:
            raise ValueError(
                "Selected Members were not all found by pointing discovery"
            )
        if len(selected) > 20:
            raise ValueError("Selected Members exceed the 20-target acceptance limit")
        discovery = dict(
            discovery,
            candidates=selected,
            candidate_count=len(selected),
            acceptance_scope="EXPLICIT_DISCOVERED_MEMBER_SUBSET",
            discovered_candidate_count=discovery["candidate_count"],
        )
        (root / "selection").mkdir()
        write_json(root / "selection/discovery.json", discovery)
    client = MetadataBundleClient(root / "metadata", live=replay is None)
    result = assess_observation(
        request["request"],
        request["search_options"],
        sources=AssessmentSources(
            "LIVE" if replay is None else "REPLAY", lambda: ArchiveInput(client)
        ),
        mosaic=MosaicAssessmentInput(
            proposed,
            output / "evaluation",
            None,
            margin_arcsec,
            preparation_directory=root / "selection",
        ),
    )
    if result.document is None:
        raise ValueError("Acceptance proposal failed validation")
    report = result.document
    write_json(output / "evaluation/assessment.json", report)
    if replay is None:
        seal(root)
    contexts = [
        c
        for item in report["candidates"]
        for c in item.get("evaluation", {}).get("contexts", [])
    ]
    summary = dict(
        schema_version="mosaic_region_acceptance_1",
        mode="OFFLINE_REPLAY" if replay else "LIVE_CAPTURE",
        scope="EXPLICIT_DISCOVERED_MEMBER_SUBSET",
        assessment_status=report["assessment_status"],
        discovery_status=discovery["status"],
        discovered_candidates=discovery["discovered_candidate_count"],
        selected_candidates=len(report["candidates"]),
        elapsed_seconds=time.monotonic() - started,
        metadata_http_requests=client.request_count,
        auxiliary_http_requests=0,
        contexts=[
            dict(
                context_id=c["context_id"],
                position=next(
                    r["outcome"]
                    for r in c["criteria"]
                    if r["criterion_id"] == "POS-MOSAIC"
                ),
                inside=c["coverage"]["inside_count"],
                total=c["coverage"]["pointing_count"],
                scope_status=c["coverage"]["scope_status"],
                branches=c["branches"],
            )
            for c in contexts
        ],
        absence_interpretation="NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION",
    )
    write_json(output / "summary.json", summary)
    return summary
