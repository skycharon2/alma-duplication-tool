"""Bind captured official AQ array labels to a reconstructed Archive source.

No network access or scientific formula belongs here. A Member-only match is
insufficient: the exact AQ source ID, Member and source name must all agree.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path

from alma_duplicate.domain.comparison import ArchiveContextEvidence

METHOD = "archive_source_array_1"
DECISION_REF = "docs/archive_array_evidence.md#source-bound-method-adoption-2026-10-02"
COMPONENTS = {"7m": "ACA_7M", "12m": "MAIN_ARRAY_12M", "tp": "TOTAL_POWER"}


@dataclass(frozen=True)
class ArrayRecord:
    observation_id: str
    member_ous_uid: str
    source_name: str
    raw_label: str | None
    response_sha256: str
    retrieved_at: str
    url: str


@dataclass(frozen=True)
class ArchiveArrayEvidence:
    context_id: str
    source_record_id: str
    manifest_sha256: str
    records: tuple[ArrayRecord, ...]
    components: tuple[str, ...]
    diameters_m: tuple[float, ...]
    reasons: tuple[str, ...]
    method_version: str = METHOD

    def total_power_at(self, diameter):
        return diameter == 12.0 and "TOTAL_POWER" in self.components


@dataclass(frozen=True)
class ArchiveArrayCatalog:
    records: tuple[ArrayRecord, ...]
    manifest_sha256: str
    input_paths: tuple[Path, ...] = ()

    def bind(self, context):
        def result(records=(), components=(), diameters=(), reasons=()):
            return ArchiveArrayEvidence(context.context_id, context.reference.source_record_id,
                                        self.manifest_sha256, records, components, diameters, reasons)
        if not isinstance(context.evidence, ArchiveContextEvidence):
            raise ValueError("Official Archive arrays cannot bind to another source")
        link = context.evidence.row_link
        if not link.is_linked:
            return result(reasons=("ARCHIVE_ARRAY_SOURCE_IDENTITY_UNRESOLVED",))
        key = link.association_key.context
        if context.evidence.prepared.raw_row.get("target_name") != key.source_name:
            return result(reasons=("ARCHIVE_ARRAY_SOURCE_NAME_CONFLICT",))
        source_id = f"{key.member_ous_uid}.source.{key.source_name}"
        # Multiple source hits (even with equal labels) require an explicit
        # disambiguation contract, rather than silently picking the first one.
        records = tuple(r for r in self.records if r.observation_id == source_id)
        if not records:
            return result(reasons=("ARCHIVE_ARRAY_EVIDENCE_MISSING",))
        if len(records) != 1:
            return result(records=records, reasons=("ARCHIVE_ARRAY_EVIDENCE_AMBIGUOUS",))
        record = records[0]
        if record.member_ous_uid != key.member_ous_uid or record.source_name != key.source_name:
            return result(records=records, reasons=("ARCHIVE_ARRAY_SOURCE_IDENTITY_CONFLICT",))
        tokens = (record.raw_label or "").lower().split()
        if not tokens or len(set(tokens)) != len(tokens) or any(t not in COMPONENTS for t in tokens):
            return result(records=records, reasons=("ARCHIVE_ARRAY_LABEL_UNSUPPORTED",))
        components = tuple(sorted(COMPONENTS[t] for t in tokens))
        diameters = tuple(sorted({7.0 if t == "7m" else 12.0 for t in tokens}))
        return result(records, components, diameters, ("OFFICIAL_AQ_SOURCE_ARRAY_BOUND",))


def load_archive_array_catalog(path):
    """Load the captured public AQ manifest; corrupt/incomplete input is an error."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("AQ array manifest must be a nonempty list")
    records, inputs = [], [path]
    try:
        for entry in manifest:
            name = entry["file"]
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError("AQ response must be a sibling file")
            response_path = (path.parent / name).resolve()
            if response_path.parent != path.parent:
                raise ValueError("AQ response must remain within its capture directory")
            data = response_path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != entry["sha256"]:
                raise ValueError("AQ response checksum mismatch")
            if entry["url"] != "https://almascience.eso.org/aq/service/api/search/observations/_search":
                raise ValueError("Unsupported AQ observation endpoint")
            captured = entry["retrieved_at"]
            if datetime.fromisoformat(captured).tzinfo is None:
                raise ValueError("AQ capture time must include timezone")
            member = entry["request_body"]["query"]["term"]["mous"]
            payload = json.loads(data)
            hits, total = payload["hits"]["hits"], payload["hits"]["total"]
            shards = payload.get("_shards", {})
            if not isinstance(shards, dict):
                raise ValueError("Invalid AQ shard status")
            if (payload.get("timed_out", False) or shards.get("failed", 0)
                    or total["relation"] != "eq" or total["value"] != len(hits)):
                raise ValueError("Incomplete AQ array evidence")
            for hit in hits:
                source = hit["_source"]
                values = (hit["_id"], source["mous"], source["sourceName"])
                label = source.get("array")
                if (not all(isinstance(v, str) and v for v in values) or source["mous"] != member
                        or (label is not None and not isinstance(label, str))):
                    raise ValueError("Malformed or incorrectly scoped AQ source record")
                records.append(ArrayRecord(*values, label, digest, captured, entry["url"]))
            inputs.append(response_path)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed AQ array manifest or response") from exc
    return ArchiveArrayCatalog(tuple(records), hashlib.sha256(raw).hexdigest(), tuple(inputs))
