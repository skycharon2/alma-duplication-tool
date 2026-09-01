"""Deterministic reconstruction of observed Queue-row associations."""

from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256

from alma_duplicate.domain.queue import (
    QueueFactorizationSummary,
    QueueGroupKey,
    QueueRawRowId,
    QueueReconstructionBatch,
    QueueRequestContext,
    QueueRequestEvidence,
    QueueRowAssociation,
    QueueSpatialComponent,
    QueueSpatialEvidence,
    QueueSpectralEvidence,
    QueueSpectralSetup,
    RegularSpwEvidence,
    SpectralScanEvidence,
)

QUEUE_RECONSTRUCTION_VERSION = "1"
QUEUE_SPATIAL_SIGNATURE_VERSION = "1"
QUEUE_SPECTRAL_SIGNATURE_VERSION = "1"
QUEUE_REQUEST_SIGNATURE_VERSION = "1"


def _group_payload(group: QueueGroupKey) -> list[str]:
    return [
        group.project_code,
        group.target_name,
        group.band,
    ]


def _raw_quantity(value) -> str | None:
    if value is None:
        return None
    return value.raw_text


def _digest(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"{prefix}:{sha256(encoded).hexdigest()}"


def _spatial_id(
    group: QueueGroupKey,
    spatial: QueueSpatialEvidence,
) -> str:
    payload = {
        "version": QUEUE_SPATIAL_SIGNATURE_VERSION,
        "group": _group_payload(group),
        "values": [
            spatial.ra_deg.raw_text,
            spatial.dec_deg.raw_text,
            spatial.ra_hms_raw,
            spatial.dec_dms_raw,
            spatial.long_offset_arcsec.raw_text,
            spatial.lat_offset_arcsec.raw_text,
            spatial.mosaic_raw,
            _raw_quantity(spatial.mosaic_length_arcsec),
            _raw_quantity(spatial.mosaic_width_arcsec),
            _raw_quantity(spatial.mosaic_pa_deg),
            _raw_quantity(spatial.mosaic_spacing_arcsec),
            spatial.coordinate_system_raw,
        ],
    }
    return _digest("queue-spatial-v1", payload)


def _sensitivity_payload(spectral: QueueSpectralEvidence) -> list[str]:
    sensitivity = spectral.sensitivity
    return [
        sensitivity.reference_frequency_ghz.raw_text,
        sensitivity.reference_width_mhz.raw_text,
        sensitivity.requested_sensitivity_mjy.raw_text,
    ]


def _velocity_payload(spectral: QueueSpectralEvidence) -> list[object]:
    velocity = spectral.velocity
    return [
        velocity.velocity_kms.raw_text,
        velocity.frame_raw,
        velocity.convention_raw,
        velocity.is_sky_frequency,
    ]


def _spectral_id(
    group: QueueGroupKey,
    spectral: QueueSpectralEvidence,
) -> str:
    if isinstance(spectral, RegularSpwEvidence):
        representation = "REGULAR_SPW"
        values = [
            [
                spw.number,
                spw.frequency_ghz.raw_text,
                spw.bandwidth_mhz.raw_text,
                spw.spectral_resolution_mhz.raw_text,
            ]
            for spw in spectral.spws
        ]
    elif isinstance(spectral, SpectralScanEvidence):
        representation = "SPECTRAL_SCAN"
        values = [
            spectral.start_frequency_ghz.raw_text,
            spectral.end_frequency_ghz.raw_text,
            spectral.per_window_bandwidth_mhz.raw_text,
            spectral.spectral_resolution_mhz.raw_text,
        ]
    else:
        raise TypeError(
            f"unsupported spectral evidence: {type(spectral)!r}"
        )

    payload = {
        "version": QUEUE_SPECTRAL_SIGNATURE_VERSION,
        "group": _group_payload(group),
        "representation": representation,
        "velocity": _velocity_payload(spectral),
        "sensitivity": _sensitivity_payload(spectral),
        "values": values,
    }
    return _digest("queue-spectral-v1", payload)


def _request_id(
    group: QueueGroupKey,
    request: QueueRequestEvidence,
) -> str:
    payload = {
        "version": QUEUE_REQUEST_SIGNATURE_VERSION,
        "group": _group_payload(group),
        "values": [
            request.requested_angular_resolution_arcsec.raw_text,
            request.requested_las_arcsec.raw_text,
            request.use_7m,
            request.use_tp,
            request.polarization_raw,
        ],
    }
    return _digest("queue-request-v1", payload)


def _row_id_sort_key(row_id: QueueRawRowId) -> tuple[str, int, int]:
    return (
        row_id.snapshot_sha256,
        row_id.physical_start_line,
        row_id.physical_end_line,
    )


def _group_sort_key(group: QueueGroupKey) -> tuple[str, str, str]:
    return (
        group.project_code,
        group.target_name,
        group.band,
    )


def reconstruct_queue_rows(
    rows,
) -> QueueReconstructionBatch:
    """Factor components while retaining source-observed links only."""

    inputs = tuple(rows)
    spatial_evidence: dict[
        str,
        tuple[QueueGroupKey, QueueSpatialEvidence],
    ] = {}
    spectral_evidence: dict[
        str,
        tuple[QueueGroupKey, QueueSpectralEvidence],
    ] = {}
    request_evidence: dict[
        str,
        tuple[QueueGroupKey, QueueRequestEvidence],
    ] = {}

    spatial_rows: dict[str, list[QueueRawRowId]] = defaultdict(list)
    spectral_rows: dict[str, list[QueueRawRowId]] = defaultdict(list)
    request_rows: dict[str, list[QueueRawRowId]] = defaultdict(list)
    associations: list[QueueRowAssociation] = []

    for row in inputs:
        spatial_id = _spatial_id(row.group_key, row.spatial)
        spectral_id = _spectral_id(row.group_key, row.spectral)
        request_id = _request_id(row.group_key, row.request)

        spatial_evidence.setdefault(
            spatial_id,
            (row.group_key, row.spatial),
        )
        spectral_evidence.setdefault(
            spectral_id,
            (row.group_key, row.spectral),
        )
        request_evidence.setdefault(
            request_id,
            (row.group_key, row.request),
        )
        spatial_rows[spatial_id].append(row.raw_row.row_id)
        spectral_rows[spectral_id].append(row.raw_row.row_id)
        request_rows[request_id].append(row.raw_row.row_id)

        associations.append(
            QueueRowAssociation(
                raw_row_id=row.raw_row.row_id,
                group_key=row.group_key,
                spatial_component_id=spatial_id,
                spectral_setup_id=spectral_id,
                request_context_id=request_id,
                content_fingerprint=(
                    row.raw_row.content_fingerprint
                ),
            )
        )

    spatial_components = tuple(
        QueueSpatialComponent(
            component_id=component_id,
            group_key=spatial_evidence[component_id][0],
            evidence=spatial_evidence[component_id][1],
            source_row_ids=tuple(
                sorted(
                    spatial_rows[component_id],
                    key=_row_id_sort_key,
                )
            ),
        )
        for component_id in sorted(spatial_evidence)
    )
    spectral_setups = tuple(
        QueueSpectralSetup(
            setup_id=setup_id,
            group_key=spectral_evidence[setup_id][0],
            evidence=spectral_evidence[setup_id][1],
            source_row_ids=tuple(
                sorted(
                    spectral_rows[setup_id],
                    key=_row_id_sort_key,
                )
            ),
        )
        for setup_id in sorted(spectral_evidence)
    )
    request_contexts = tuple(
        QueueRequestContext(
            context_id=context_id,
            group_key=request_evidence[context_id][0],
            evidence=request_evidence[context_id][1],
            source_row_ids=tuple(
                sorted(
                    request_rows[context_id],
                    key=_row_id_sort_key,
                )
            ),
        )
        for context_id in sorted(request_evidence)
    )
    canonical_associations = tuple(
        sorted(
            associations,
            key=lambda association: _row_id_sort_key(
                association.raw_row_id
            ),
        )
    )

    by_group: dict[
        QueueGroupKey,
        list[QueueRowAssociation],
    ] = defaultdict(list)
    for association in canonical_associations:
        by_group[association.group_key].append(association)

    factorization: list[QueueFactorizationSummary] = []
    for group in sorted(by_group, key=_group_sort_key):
        group_associations = by_group[group]
        spatial_ids = {
            association.spatial_component_id
            for association in group_associations
        }
        spectral_ids = {
            association.spectral_setup_id
            for association in group_associations
        }
        observed_pairs = {
            (
                association.spatial_component_id,
                association.spectral_setup_id,
            )
            for association in group_associations
        }
        observed_triplets = {
            (
                association.spatial_component_id,
                association.spectral_setup_id,
                association.request_context_id,
            )
            for association in group_associations
        }
        factorization.append(
            QueueFactorizationSummary(
                group_key=group,
                raw_row_count=len(group_associations),
                spatial_component_count=len(spatial_ids),
                spectral_setup_count=len(spectral_ids),
                observed_pair_count=len(observed_pairs),
                potential_pair_count=(
                    len(spatial_ids) * len(spectral_ids)
                ),
                repeated_association_count=(
                    len(group_associations)
                    - len(observed_triplets)
                ),
            )
        )

    return QueueReconstructionBatch(
        spatial_components=spatial_components,
        spectral_setups=spectral_setups,
        request_contexts=request_contexts,
        associations=canonical_associations,
        factorization=tuple(factorization),
        reconstruction_version=QUEUE_RECONSTRUCTION_VERSION,
    )
