"""Project-approved operational UI mapping, scoped to a Source-SPW association.

This is not a universal claim about physical correlator configurations.
"""

from numbers import Integral
from collections.abc import Iterable
from alma_duplicate.clients.archive_contract import TapFieldMetadata
from alma_duplicate.domain.reconstruction import SourceSpwAssociationKey

import numpy as np

from alma_duplicate.domain.line_evidence import ArchiveModeEvidence, ModeObservation


def derive_archive_mode(
    source_record_id: str,
    association: SourceSpwAssociationKey | None,
    rows: Iterable[tuple[str, object]],
    field_metadata: tuple[TapFieldMetadata, ...],
) -> ArchiveModeEvidence:
    """Rows are (raw_row_id, raw em_xel) pairs from one reconstructed association."""
    descriptors = [f for f in field_metadata if f.name.casefold() == "em_xel"]
    field = descriptors[0] if len(descriptors) == 1 else None
    if not descriptors:
        metadata_status = "MISSING_FIELD_METADATA"
    elif len(descriptors) != 1:
        metadata_status = "AMBIGUOUS_FIELD_METADATA"
    elif (
        field.datatype.strip().lower() not in {"short", "int", "long"}
        or (field.arraysize or "").strip() not in {"", "1"}
        or (field.unit or "").strip() not in {"", "1"}
    ):
        metadata_status = "INCOMPATIBLE_FIELD_METADATA"
    else:
        metadata_status = "VERIFIED_INTEGER_SCALAR"
    observations = []
    for row_id, raw in rows:
        count = None
        if raw is np.ma.masked:
            status, stored_raw = "MASKED_COUNT", None
        elif raw is None:
            status, stored_raw = "MISSING_COUNT", None
        elif (
            isinstance(raw, (bool, np.bool_))
            or not isinstance(raw, Integral)
            or raw <= 0
        ):
            status, stored_raw = "INVALID_COUNT", raw
        else:
            count = int(raw)
            status, stored_raw = "AVAILABLE", raw
        raw_type = type(raw).__name__
        if isinstance(stored_raw, np.generic):
            stored_raw = stored_raw.item()
        if stored_raw is not None and type(stored_raw) not in (bool, int, float, str):
            # Unsupported raw scalar representations remain explicit diagnostic text.
            stored_raw = repr(stored_raw)
        known = count is not None and metadata_status == "VERIFIED_INTEGER_SCALAR"
        observations.append(
            ModeObservation(
                row_id,
                stored_raw,
                status,
                count,
                raw_type,
                ("CONTINUUM" if count <= 128 else "LINE") if known else "UNKNOWN",
                ("TDM" if count <= 128 else "FDM") if known else "UNKNOWN",
            )
        )
    reasons = []
    if metadata_status != "VERIFIED_INTEGER_SCALAR":
        reasons.append(metadata_status)
    if association is None:
        reasons.append("SOURCE_SPW_ASSOCIATION_UNAVAILABLE")
    if not observations:
        reasons.append("NO_MODE_OBSERVATIONS")
    reasons.extend(o.status for o in observations if o.status != "AVAILABLE")
    if len({o.channel_count for o in observations if o.channel_count is not None}) > 1:
        reasons.append("CONFLICTING_ASSOCIATION_COUNTS")
    known = not reasons
    return ArchiveModeEvidence(
        source_record_id,
        association,
        tuple(observations),
        metadata_status,
        "AVAILABLE" if known else "UNKNOWN",
        observations[0].ui_type if known else "UNKNOWN",
        observations[0].operational_mode if known else "UNKNOWN",
        tuple(dict.fromkeys(reasons)),
        field.datatype if field else None,
        field.unit if field else None,
        field.arraysize if field else None,
    )
