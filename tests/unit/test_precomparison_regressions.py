"""Regressions for evidence validation before comparison modeling."""
from __future__ import annotations

import csv
import io
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from alma_duplicate.clients.archive_contract import TapFieldMetadata
from alma_duplicate.clients.archive_field_contract import (
    ARCHIVE_COMPARISON_FIELD_SPECS,
    build_archive_comparison_evidence,
    validate_archive_comparison_metadata,
)
from alma_duplicate.clients.queue_csv_adapter import run_queue_pipeline
from alma_duplicate.domain.archive_evidence import ArchiveQuantityStatus
from alma_duplicate.domain.queue import (
    QueueIssueKind,
    QueueParseStatus,
    QueueUsableBandwidthDerivationKind,
    RegularSpwEvidence,
)
from alma_duplicate.domain.reconstruction import ArchiveRowInput, SupportMappingStatus
from alma_duplicate.parsers.frequency_support import parse_frequency_support
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.reconstruction import reconstruct_archive_rows

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def _queue_with_changes(changes: dict[str, str], *, sps: bool = False):
    records = list(csv.reader(io.StringIO(FIXTURE.read_text(encoding="utf-8-sig"))))
    header = next(i for i, row in enumerate(records) if "Freq SPW 1" in row)
    columns = {name: i for i, name in enumerate(records[header])}
    rows = records[header + 2:]
    row = next(row for row in rows if bool(row[columns["Freq SPW 1"]].strip()) != sps)
    for name, value in changes.items():
        row[columns[name]] = value
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(records)
    return parse_queue_csv_bytes(stream.getvalue().encode())


@pytest.mark.parametrize("raw", [
    "[100..101GHz, -1kHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "[100..101GHz, 1kHz, -1mJy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "[100..101GHz, 1kHz, 1mJy/beam@10km/s, 0mJy/beam@native, XX YY]",
    "[100..1e999GHz, 1kHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "[100..101GHz, 1e999kHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "[1e-320..2e-320Hz, 1kHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "[100..101GHz, 1kHz, 1e308Jy/beam@10km/s, 1mJy/beam@native, XX YY]",
    "{100GHz, 1MHz, -1mJy/beam@10km/s, 1mJy/beam@native, XX YY}",
    "{1e999GHz, 1MHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY}",
    "{100GHz, 0MHz, 1mJy/beam@10km/s, 1mJy/beam@native, XX YY}",
])
def test_invalid_spectral_numbers_remain_evidence_but_cannot_be_mapped(raw):
    parsed = parse_frequency_support(raw)
    assert parsed.raw_value == raw
    assert parsed.components
    assert not parsed.is_valid
    row = ArchiveRowInput(
        raw_row_id="invalid-numeric",
        member_ous_uid="uid://A001/X3955/X44",
        asdm_uid="uid://A002/X123/X456",
        obs_id="uid://A001/X3955/X44.source.Target.spw.0",
        frequency_ghz=100.5,
        frequency_support=raw,
    )
    result = reconstruct_archive_rows([row])
    assert result.linked_row_count == 1
    assert result.support_mappings[0].status is SupportMappingStatus.SUPPORT_PARSE_UNSAFE


@pytest.mark.parametrize("boolean", [True, False, np.bool_(True), np.bool_(False)])
def test_boolean_archive_quantity_is_not_numeric_evidence(boolean):
    metadata = tuple(TapFieldMetadata(
        name=spec.name, datatype="double", arraysize=None, unit=spec.expected_unit,
        ucd=None, utype=None, xtype=None, description=None,
    ) for spec in ARCHIVE_COMPARISON_FIELD_SPECS)
    evidence = build_archive_comparison_evidence(
        {"frequency": boolean, "bandwidth": 200_000_000.0,
         "spectral_resolution": 976.56, "spatial_resolution": 0.5,
         "sensitivity_10kms": 1.0, "cont_sensitivity_bandwidth": 0.2},
        validate_archive_comparison_metadata(metadata),
        query_run_id="boolean", raw_row_id="boolean:0", result_index=0,
    )
    assert evidence.frequency.centre.status is ArchiveQuantityStatus.INVALID_VALUE
    assert not evidence.has_frequency_coverage


@pytest.mark.parametrize("width", ["58.55", "58.65", "1874.99999"])
def test_bandwidth_recognition_never_enlarges_source_width(width):
    result = _queue_with_changes({"Bandwidth SPW 1": width})
    assert result.can_reconstruct
    spw = result.row_inputs[0].spectral.spws[0]
    assert spw.usable_bandwidth_ghz <= spw.nominal_bandwidth_ghz
    assert spw.usable_bandwidth_ghz == pytest.approx(float(width) / 1000)


@pytest.mark.parametrize("width", ["63", "750"])
def test_unknown_usable_bandwidth_preserves_row_and_pipeline(width):
    result = _queue_with_changes({"Bandwidth SPW 1": width})
    assert result.can_reconstruct
    assert len(result.raw_rows) == len(result.row_inputs) == 13
    assert QueueIssueKind.USABLE_BANDWIDTH_UNAVAILABLE in {i.kind for i in result.issues}
    spw = result.row_inputs[0].spectral.spws[0]
    assert spw.nominal_bandwidth_ghz == pytest.approx(float(width) / 1000)
    assert spw.usable_bandwidth_ghz is None
    assert spw.usable_lower_sky_frequency_ghz is None
    assert spw.usable_upper_sky_frequency_ghz is None
    assert spw.usable_bandwidth_derivation_kind is QueueUsableBandwidthDerivationKind.UNRECOGNIZED
    assert len(run_queue_pipeline(result).reconstruction.associations) == 13


@pytest.mark.parametrize("sps", [False, True])
def test_unverified_reference_association_does_not_drop_rows(sps):
    result = _queue_with_changes({"Ref.Frequency": "1"}, sps=sps)
    assert result.can_reconstruct
    assert QueueIssueKind.REFERENCE_FREQUENCY_ASSOCIATION_UNVERIFIED in {
        i.kind for i in result.issues
    }
    assert len(run_queue_pipeline(result).reconstruction.associations) == 13


def test_declared_sky_frequency_does_not_require_unused_doppler_fields():
    result = _queue_with_changes({
        "Is Sky Freq?": "True", "Velocity": "", "Vel. Frame": "", "Vel. Convention": "",
    })
    assert result.can_reconstruct
    spectral = result.row_inputs[0].spectral
    assert isinstance(spectral, RegularSpwEvidence)
    assert spectral.velocity.velocity_kms is None
    assert spectral.spws[0].frequency_derivation.sky_frequency_ghz == spectral.spws[0].frequency_ghz.value
    assert len(run_queue_pipeline(result).reconstruction.associations) == 13


@pytest.mark.parametrize("changes", [
    {"Is Sky Freq?": "False", "Velocity": "", "Vel. Frame": "LSRK", "Vel. Convention": "RADIO"},
    {"Is Sky Freq?": "True", "Velocity": "not-a-number"},
    {"Is Sky Freq?": ""},
    {"Is Sky Freq?": "False", "Vel. Convention": "UNKNOWN"},
])
def test_missing_required_or_malformed_doppler_evidence_remains_an_error(changes):
    result = _queue_with_changes(changes)
    assert result.status is QueueParseStatus.ERROR
    assert not result.can_reconstruct


@pytest.mark.parametrize("changes", [
    {"usable_lower_sky_frequency_ghz": None},
    {"usable_bandwidth_ghz": None, "usable_lower_sky_frequency_ghz": None,
     "usable_upper_sky_frequency_ghz": None},
    {"usable_bandwidth_derivation_kind": QueueUsableBandwidthDerivationKind.UNRECOGNIZED},
    {"usable_bandwidth_ghz": 100.0},
    {"upper_sky_frequency_ghz": float("inf")},
])
def test_spw_model_rejects_inconsistent_coverage(changes):
    spw = _queue_with_changes({}).row_inputs[0].spectral.spws[0]
    with pytest.raises(ValueError):
        replace(spw, **changes)
