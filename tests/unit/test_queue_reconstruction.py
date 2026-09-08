from __future__ import annotations

from pathlib import Path
from dataclasses import replace

import pytest

from alma_duplicate.domain.queue import QueueGroupKey
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.queue_reconstruction import reconstruct_queue_rows

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "queue"
    / "queue_pipeline_v1.csv"
)


def _batch():
    result = parse_queue_csv_bytes(FIXTURE_PATH.read_bytes())
    assert result.can_reconstruct
    return result, reconstruct_queue_rows(result.row_inputs)


def test_repeated_raw_row_identity_is_rejected_before_factorization():
    result, _ = _batch()
    row = result.row_inputs[0]
    for rows in ([row, row], iter([row, replace(row)])):
        with pytest.raises(ValueError, match="raw-row IDs must be unique"):
            reconstruct_queue_rows(rows)


def test_empty_batch_and_unique_generator_are_supported():
    result, _ = _batch()
    empty = reconstruct_queue_rows(iter(()))
    assert empty.associations == ()
    batch = reconstruct_queue_rows(iter(result.row_inputs))
    assert len(batch.associations) == 13
    assert batch.reconstruction_version == "2"


def test_reconstruction_retains_one_association_per_source_row() -> None:
    result, batch = _batch()

    assert len(batch.associations) == len(result.raw_rows) == 13
    assert {association.raw_row_id for association in batch.associations} == {
        row.row_id for row in result.raw_rows
    }
    assert batch.sparse_group_count == 2


def test_sparse_group_does_not_create_cartesian_pairs() -> None:
    _, batch = _batch()
    key = QueueGroupKey(
        project_code="2025.1.00539.S",
        target_name="M33",
        band="ALMA_RB_06",
    )
    summary = next(
        item for item in batch.factorization if item.group_key == key
    )

    assert summary.raw_row_count == 6
    assert summary.spatial_component_count == 5
    assert summary.spectral_setup_count == 5
    assert summary.observed_pair_count == 5
    assert summary.potential_pair_count == 25
    assert summary.repeated_association_count == 1

    observed = {
        (item.spatial_component_id, item.spectral_setup_id)
        for item in batch.associations
        if item.group_key == key
    }
    assert len(observed) == 5


def test_exact_export_duplicate_is_not_deleted() -> None:
    _, batch = _batch()
    repeated = {}
    for association in batch.associations:
        repeated.setdefault(
            association.content_fingerprint,
            [],
        ).append(association)
    duplicate_group = next(
        values for values in repeated.values() if len(values) == 2
    )

    assert len(duplicate_group) == 2
    assert duplicate_group[0].raw_row_id != duplicate_group[1].raw_row_id
    assert duplicate_group[0].spatial_component_id == (
        duplicate_group[1].spatial_component_id
    )
    assert duplicate_group[0].spectral_setup_id == (
        duplicate_group[1].spectral_setup_id
    )


def test_reconstruction_is_shuffle_invariant() -> None:
    result, batch = _batch()

    reversed_batch = reconstruct_queue_rows(
        reversed(result.row_inputs)
    )

    assert reversed_batch == batch
