from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from alma_duplicate.clients.queue_csv_adapter import run_queue_pipeline
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.domain.queue import (
    QueueIssueKind,
    QueueParseStatus,
    RegularSpwEvidence,
    SpectralScanEvidence,
)
from alma_duplicate.queue_csv_contract import (
    QUEUE_EVIDENCE_SNAPSHOT_SHA256,
)
from alma_duplicate.queue_normalization import (
    QUEUE_FREQUENCY_DERIVATION_VERSION,
    QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
)


@pytest.mark.snapshot
def test_pinned_full_queue_snapshot() -> None:
    raw_path = os.environ.get("ALMA_QUEUE_CSV_SNAPSHOT")
    if not raw_path:
        pytest.skip(
            "set ALMA_QUEUE_CSV_SNAPSHOT to the pinned full CSV"
        )

    path = Path(raw_path)
    result = QueueCsvClient().load(path)

    assert result.snapshot.snapshot_sha256 == (
        QUEUE_EVIDENCE_SNAPSHOT_SHA256
    )
    assert result.status is QueueParseStatus.COMPLETE_WITH_WARNINGS
    assert len(result.snapshot.operational_columns) == 79
    assert len(result.field_metadata) == 79
    assert len(result.raw_rows) == len(result.row_inputs) == 3200
    assert [issue.kind for issue in result.issues] == [
        QueueIssueKind.CONFLICTING_UNIT_DECLARATION
    ]

    assert sum(
        isinstance(row.spectral, RegularSpwEvidence)
        for row in result.row_inputs
    ) == 3199
    assert sum(
        isinstance(row.spectral, SpectralScanEvidence)
        for row in result.row_inputs
    ) == 1
    assert sum(
        len(row.spectral.spws)
        for row in result.row_inputs
        if isinstance(row.spectral, RegularSpwEvidence)
    ) == 16216

    high_redshift_rows = [
        row
        for row in result.row_inputs
        if (
            row.group_key.project_code == "2025.1.00806.S"
            and row.group_key.target_name == "CAPERS_UDS_z11"
        )
    ]
    assert len(high_redshift_rows) == 1
    high_redshift_spectral = high_redshift_rows[0].spectral
    assert isinstance(high_redshift_spectral, RegularSpwEvidence)
    assert [
        spw.nominal_bandwidth_ghz
        for spw in high_redshift_spectral.spws
    ] == pytest.approx([1.875] * 4)
    assert [
        spw.usable_bandwidth_ghz
        for spw in high_redshift_spectral.spws
    ] == pytest.approx([1.875] * 4)
    assert [
        spw.spectral_resolution_mhz.value
        for spw in high_redshift_spectral.spws
    ] == pytest.approx([7.81201171875] * 4)
    assert {
        spw.frequency_derivation.derivation_version
        for spw in high_redshift_spectral.spws
    } == {QUEUE_FREQUENCY_DERIVATION_VERSION}
    assert {
        spw.usable_bandwidth_derivation_version
        for spw in high_redshift_spectral.spws
    } == {QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION}
    assert [
        spw.frequency_derivation.sky_frequency_ghz
        for spw in high_redshift_spectral.spws
    ] == pytest.approx(
        [
            294.6701839663105,
            292.82012002706637,
            282.81977440953057,
            280.96971047028603,
        ]
    )

    all_regular_spws = [
        spw
        for row in result.row_inputs
        if isinstance(row.spectral, RegularSpwEvidence)
        for spw in row.spectral.spws
    ]
    assert all(
        spw.usable_bandwidth_ghz <= spw.nominal_bandwidth_ghz
        for spw in all_regular_spws
    )
    assert Counter(
        (
            spw.bandwidth_mhz.value,
            spw.usable_bandwidth_ghz * 1000.0,
        )
        for spw in all_regular_spws
    ) == Counter(
        {
            (62.5, 58.6): 12561,
            (125.0, 117.2): 1353,
            (250.0, 234.4): 277,
            (500.0, 468.8): 63,
            (1000.0, 937.5): 47,
            (1875.0, 1875.0): 1915,
        }
    )

    content_counts = Counter(
        row.content_fingerprint for row in result.raw_rows
    )
    assert len(content_counts) == 3135
    assert sum(count > 1 for count in content_counts.values()) == 10
    assert sum(
        count for count in content_counts.values() if count > 1
    ) == 75
    assert sum(count - 1 for count in content_counts.values()) == 65

    reconstruction = run_queue_pipeline(result).reconstruction
    assert len(reconstruction.associations) == 3200
    assert len(reconstruction.factorization) == 419
    assert reconstruction.sparse_group_count == 2
    assert sum(
        item.repeated_association_count > 0
        for item in reconstruction.factorization
    ) == 5
    assert sum(
        item.repeated_association_count
        for item in reconstruction.factorization
    ) == 65
