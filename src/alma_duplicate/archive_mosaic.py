"""Reconstruct one source execution from local Archive evidence.

Metadata is caller-supplied and retained as such. This function does not verify
remote acquisition or combine different executions, sources, or products.
"""
import re

from alma_duplicate.domain.archive_mosaic import ArchiveMosaicExecution
from alma_duplicate.parsers.archive_listobs import parse_science_fields


def reconstruct_archive_mosaic(
    raw: bytes, *, project_code: str, member_ous_uid: str, asdm_uid: str,
    source_name: str, metadata_reference: str,
    array_label: str | None = None, array_evidence_reference: str | None = None,
) -> ArchiveMosaicExecution:
    """Return execution-local evidence; never infer Member completeness."""
    for name, value in (("project_code", project_code),
                        ("metadata_reference", metadata_reference)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing {name}")
    if not re.fullmatch(r"uid://A[0-9A-Za-z]+/[0-9A-Za-z]+/[0-9A-Za-z]+", member_ous_uid):
        raise ValueError("Invalid Member UID")
    if array_label not in (None, "7m", "12m"):
        raise ValueError("Unsupported array label")
    if (array_label is None) != (array_evidence_reference is None):
        raise ValueError("Array label and evidence reference must be supplied together")
    if array_evidence_reference is not None and not array_evidence_reference.strip():
        raise ValueError("Empty array evidence reference")
    evidence = parse_science_fields(raw, asdm_uid=asdm_uid, target_name=source_name)
    return ArchiveMosaicExecution(
        project_code, member_ous_uid, asdm_uid, source_name, metadata_reference,
        evidence, array_label, array_evidence_reference,
    )
