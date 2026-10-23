"""Fail-closed binding of saved Mosaic readiness to a verified package and AQ catalog.

This is local receipt consistency, not proof that the upstream Archive is complete.
"""

import json
from pathlib import Path

from alma_duplicate.archive_array_evidence import (
    ArchiveArrayCatalog,
    ArchiveArrayCatalogMode,
    ArchiveArrayCatalogProvenance,
    ArrayRecord,
)
from alma_duplicate.archive_mosaic_readiness import build_readiness


def load_candidate_catalog(candidate: dict, *, fallback=None):
    """Prefer the candidate-local AQ receipt that was used for readiness."""
    path = Path(candidate["directory"]) / "array_acquisition.json"
    if not path.exists():
        return fallback
    saved = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(saved.get("records"), list):
        raise ValueError("Candidate AQ acquisition records are missing")
    provenance = saved["provenance"]
    if provenance["mode"] != "LIVE":
        raise ValueError("Candidate-local acquisition must have LIVE AQ provenance")
    return ArchiveArrayCatalog(
        tuple(ArrayRecord(**row) for row in saved["records"]),
        ArchiveArrayCatalogProvenance(
            ArchiveArrayCatalogMode(provenance["mode"]),
            provenance.get("manifest_sha256"),
        ),
    )


def verify_candidate_readiness(candidate: dict, *, catalog) -> set[str]:
    """Reparse verified package bytes and reject stale/edited readiness receipts.

    Never infer a ready execution merely from a saved JSON flag. The rebuilt
    readiness must agree exactly with its saved local counterpart.
    """
    package_dir = Path(candidate["package_audit_dir"])
    saved = json.loads(Path(candidate["readiness_file"]).read_text(encoding="utf-8"))
    rebuilt = build_readiness(package_dir, catalog=catalog)
    key = (candidate["member_ous_uid"], candidate["source_name"])
    if (rebuilt["member_ous_uid"], rebuilt["source_name"]) != key:
        raise ValueError("Reconstructed readiness belongs to another candidate")
    if saved != rebuilt:
        raise ValueError("Saved Mosaic readiness differs from verified package/AQ evidence")
    seen = set()
    ready = set()
    for execution in rebuilt["executions"]:
        uid = execution["asdm_uid"]
        if not isinstance(uid, str) or not uid or uid in seen:
            raise ValueError("Invalid or repeated readiness execution identity")
        seen.add(uid)
        fields = execution["fields"]
        if fields and all(
            field["position_status"] == "EVIDENCE_BOUND" for field in fields
        ):
            ready.add(uid)
    return ready
