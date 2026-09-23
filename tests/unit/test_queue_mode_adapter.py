from dataclasses import replace

import pytest

import alma_duplicate.queue_mode_adapter as adapter
from alma_duplicate.queue_processor_mode import configurations


def derive(cycle=12, pol="DOUBLE", bw=1875.0, resolution=7.81201171875, **kwargs):
    return adapter.derive_mode(
        cycle,
        pol,
        bw,
        resolution,
        processor_scope=kwargs.get(
            "processor_scope", adapter.ProcessorScope.INTERFEROMETRIC
        ),
    )


@pytest.mark.parametrize(
    "cycle,pol,resolution",
    [
        (11, "FULL", 15.6240234375),
        (12, "DOUBLE", 7.81201171875),
        (12, "DOUBLE", 7.812011718750001),
        (12, "FULL", 15.6240234375),
    ],
)
def test_reviewed_raw_signatures(cycle, pol, resolution):
    result = derive(cycle, pol, resolution=resolution)
    assert result["mode"] == "FDM"
    assert result["match_path"] == "N16_SCOPED_COMPATIBILITY"
    assert result["compatible_modes"] == ["FDM"]
    assert result["input"]["resolution_mhz"] == resolution
    assert result["classification_relative_bound"] == "1/16000"
    assert result["evidence_origin"] == "DERIVED"
    assert result["export_provenance"] == "UNRESOLVED"
    assert not any(c["export_compatibility"] for c in result["matched_configurations"])
    reference = [
        c
        for c in configurations(cycle)
        if c.polarization == pol
        and c.bandwidth_mhz == 1875
        and not c.export_compatibility
    ]
    # Independent fixed-space exclusion, not an assertion on adapter-filtered matches.
    tdm = [
        abs(resolution - c.resolution_mhz) / c.resolution_mhz
        for c in reference
        if c.mode == "TDM"
    ]
    assert min(tdm) > 0.58


@pytest.mark.parametrize("cycle", [11, 12, 13])
@pytest.mark.parametrize(
    "pol,multiplier", [("SINGLE", 0.5), ("DOUBLE", 1), ("FULL", 2)]
)
def test_reference_fdm_tdm_exact_priority(cycle, pol, multiplier):
    for resolution, mode in [(7.8125 * multiplier, "FDM"), (31.25 * multiplier, "TDM")]:
        r = derive(cycle, pol, resolution=resolution)
        assert r["mode"] == mode
        assert r["match_path"] == "EXACT_REFERENCE"
        assert r["classification_relative_bound"] is None


@pytest.mark.parametrize(
    "cycle,pol", [(11, "DOUBLE"), (13, "DOUBLE"), (13, "FULL"), (12, "SINGLE")]
)
def test_unreviewed_combinations_never_use_fallback(cycle, pol):
    resolution = (
        15.6240234375
        if pol == "FULL"
        else 3.906005859375
        if pol == "SINGLE"
        else 7.81201171875
    )
    r = derive(cycle, pol, resolution=resolution)
    assert r["mode"] == "UNKNOWN"
    assert r["reason"] == "OUTSIDE_N16_COMPATIBILITY_SCOPE"


@pytest.mark.parametrize(
    "resolution,mode",
    [
        (7.81201171875, "FDM"),
        (7.81225, "FDM"),
        (7.8125, "FDM"),
        (7.8120117, "UNKNOWN"),
        (7.8125001, "UNKNOWN"),
        (10.0, "UNKNOWN"),
    ],
)
def test_bounded_input_gate(resolution, mode):
    assert derive(resolution=resolution)["mode"] == mode


def test_unknown_processor_scope():
    assert (
        derive(processor_scope=adapter.ProcessorScope.UNRESOLVED)["mode"] == "UNKNOWN"
    )


@pytest.mark.parametrize("value", [None, 0, -1, float("nan"), float("inf"), True])
def test_invalid_numerical_evidence(value):
    assert derive(resolution=value)["reason"] == "INVALID_OR_MISSING_NUMERICAL_EVIDENCE"


def test_competing_tdm_within_compatibility_bound_is_not_filtered_out(monkeypatch):
    rows = configurations(12)
    anchor = next(
        c
        for c in rows
        if c.polarization == "DOUBLE"
        and c.resolution_mhz == 7.8125
        and c.weighting == "HANNING"
        and c.averaging == 16
    )
    rival = replace(
        anchor,
        configuration_id="synthetic_tdm_competitor",
        mode="TDM",
        resolution_mhz=7.8124,
        weighting="UNIFORM",
    )
    monkeypatch.setattr(adapter, "configurations", lambda cycle: rows + (rival,))
    r = derive()
    assert r["mode"] == "UNKNOWN"
    assert r["compatible_modes"] == ["FDM", "TDM"]
    assert r["reason"] == "COMPETING_MODES"


def test_exact_ambiguity_never_falls_back(monkeypatch):
    rows = configurations(12)
    anchor = next(
        c for c in rows if c.polarization == "DOUBLE" and c.resolution_mhz == 7.8125
    )
    rival = replace(anchor, configuration_id="synthetic_exact_tdm", mode="TDM")
    monkeypatch.setattr(adapter, "configurations", lambda cycle: rows + (rival,))
    r = derive(resolution=7.8125)
    assert r["mode"] == "UNKNOWN"
    assert r["match_path"] == "EXACT_REFERENCE"


def test_missing_catalog_and_wrong_bandwidth(monkeypatch):
    assert derive(bw=1000)["mode"] == "UNKNOWN"
    monkeypatch.setattr(adapter, "configurations", lambda cycle: ())
    assert derive()["mode"] == "UNKNOWN"


def test_no_global_tolerance_or_old_experiment_change():
    from alma_duplicate.queue_processor_mode import evaluate
    from alma_duplicate.queue_mode import REL_TOL, ABS_TOL_MHZ

    assert REL_TOL == ABS_TOL_MHZ == 1e-12
    old = evaluate(12, "DOUBLE", 1875.0, 7.81201171875, require_tp=False)
    assert old["formal_mode"] == "UNKNOWN"
    assert old["matched_configuration_ids"] == []


@pytest.mark.parametrize("cycle", [11, 12, 13])
def test_tp_equivalence_and_mapping_block(cycle):
    scope = adapter.ProcessorScope.REQUESTED_TP_EQUIVALENCE
    r = derive(cycle=cycle, resolution=31.25, processor_scope=scope)
    assert r["mode"] == "TDM"
    assert r["processor_mappings"]
    assert r["processor_evidence"] == "CONDITIONAL_EQUIVALENCE_MAPPING"
    assert not r["enumeration_complete"]
    assert (
        derive(cycle=cycle, pol="FULL", resolution=62.5, processor_scope=scope)[
            "reason"
        ]
        == "FULL_POLARIZATION_TP_UNSUPPORTED"
    )
    r = derive(cycle=cycle, bw=1000, resolution=2.2578125, processor_scope=scope)
    assert r["mode"] == "UNKNOWN"
    assert r["reason"] == "PROCESSOR_MAPPING_INCOMPLETE"


def test_tp_mapping_missing_is_not_silently_ignored(monkeypatch):
    monkeypatch.setattr(adapter, "_mapping_probe", lambda *args: {"tps_mappings": []})
    r = derive(
        resolution=31.25,
        processor_scope=adapter.ProcessorScope.REQUESTED_TP_EQUIVALENCE,
    )
    assert r["mode"] == "UNKNOWN"
    assert r["reason"] == "PROCESSOR_MAPPING_INCOMPLETE"


def test_geometry_is_not_a_classifier_argument():
    import inspect

    assert "geometry" not in inspect.signature(adapter.derive_mode).parameters
    assert (
        adapter.single_point_applicability("SINGLE_FIELD", False)["status"]
        == "SUPPORTED"
    )
    assert (
        adapter.single_point_applicability("RECTANGULAR_MOSAIC", False)["status"]
        == "UNSUPPORTED"
    )
    assert (
        adapter.single_point_applicability("UNKNOWN", False)["status"]
        == "INDETERMINATE"
    )
    assert (
        adapter.single_point_applicability("SINGLE_FIELD", True)["status"]
        == "UNSUPPORTED"
    )
    assert (
        adapter.single_point_applicability("SINGLE_FIELD", None)["status"]
        == "INDETERMINATE"
    )


def test_typed_row_binding_and_geometry_independence():
    from pathlib import Path
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    from alma_duplicate.domain.queue import QueueMosaicKind, RegularSpwEvidence

    parsed = QueueCsvClient().load(
        Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"
    )
    row = next(
        r for r in parsed.row_inputs if isinstance(r.spectral, RegularSpwEvidence)
    )
    first = row.spectral.spws[0]
    single = replace(
        row,
        spatial=replace(row.spatial, mosaic_kind=QueueMosaicKind.SINGLE_FIELD),
        request=replace(row.request, use_tp=False),
    )
    mosaic = replace(
        single,
        spatial=replace(single.spatial, mosaic_kind=QueueMosaicKind.RECTANGULAR_MOSAIC),
    )
    a, b = (
        adapter.classify_spw(single, first.number),
        adapter.classify_spw(mosaic, first.number),
    )
    assert a["mode_evidence"] == b["mode_evidence"]
    assert a["single_point_applicability"]["status"] == "SUPPORTED"
    assert b["single_point_applicability"]["status"] == "UNSUPPORTED"
    assert a["source"]["source_row_id"] == single.raw_row.row_id.value
    assert a["source"]["resolution_raw_mhz"] == first.spectral_resolution_mhz.raw_text
    with pytest.raises(ValueError, match="SPW_SLOT_NOT_UNIQUELY_BOUND"):
        adapter.classify_spw(single, 999)
    duplicated = replace(single, spectral=replace(single.spectral, spws=(first, first)))
    with pytest.raises(ValueError, match="SPW_SLOT_NOT_UNIQUELY_BOUND"):
        adapter.classify_spw(duplicated, first.number)
    # A different row with the same slot retains its own numerical evidence.
    other = replace(
        first,
        spectral_resolution_mhz=replace(
            first.spectral_resolution_mhz, value=123.456, raw_text="123.456"
        ),
    )
    other_id = replace(
        single.raw_row.row_id,
        physical_start_line=single.raw_row.row_id.physical_start_line + 100,
        physical_end_line=single.raw_row.row_id.physical_end_line + 100,
    )
    alternate = replace(
        single,
        raw_row=replace(single.raw_row, row_id=other_id),
        spectral=replace(single.spectral, spws=(other,)),
    )
    changed = adapter.classify_spw(alternate, first.number)
    assert changed["mode_evidence"]["input"]["resolution_mhz"] == 123.456
    assert changed["mode_evidence"]["mode"] == "UNKNOWN"
    assert changed["source"]["source_row_id"] != a["source"]["source_row_id"]
