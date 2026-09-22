from dataclasses import replace

import pytest

from alma_duplicate.data.correlator_modes import configurations
from alma_duplicate.queue_mode import derive_queue_mode, project_cycle


@pytest.mark.parametrize(
    "pol,bw,res,mode",
    [
        ("DOUBLE", 1875, 31.25, "TDM"),
        ("DOUBLE", 1875, 36.125, "TDM"),
        ("DOUBLE", 1875, 7.81201171875, "FDM"),
        ("DOUBLE", 1875, 7.812011718750001, "FDM"),
        ("DOUBLE", 62.5, 0.070556640625, "FDM"),
        ("FULL", 1875, 15.6240234375, "FDM"),
        ("FULL", 1875, 62.5, "TDM"),
        ("DOUBLE", 1000, 2.2578125, "FDM"),
    ],
)
def test_supplied_examples_and_real_signatures(pol, bw, res, mode):
    e = derive_queue_mode(12, pol, bw, res)
    assert e.unique_configuration_mode == mode
    assert e.conditional_mode_consensus == mode
    assert e.source_bound_mode == "UNKNOWN"
    assert e.source_bound_reason == "PROCESSOR_ASSOCIATION_UNRESOLVED"
    assert e.evidence_origin == "APPLICATION_DERIVED"
    assert e.method_status == "PROVISIONAL"
    assert len(e.matched_configurations) == 1


def test_full_polarization_would_fail_fake_channel_threshold():
    e = derive_queue_mode(11, "FULL", 1875, 15.6240234375)
    assert 1875 / 15.6240234375 < 129
    assert e.unique_configuration_mode == "FDM"
    assert e.matched_configurations[0].averaging == 16
    assert "queue_export_n16" in e.matched_configurations[0].source_id


@pytest.mark.parametrize("res,count", [(0.06103515625, 2), (0.14111328125, 2)])
def test_same_mode_multiple_configurations_stay_ambiguous(res, count):
    e = derive_queue_mode(12, "DOUBLE", 62.5, res)
    assert e.unique_configuration_mode == "UNKNOWN"
    assert e.configuration_reason == "AMBIGUOUS_CONFIGURATION"
    assert e.configuration_status == "AMBIGUOUS"
    assert e.conditional_mode_consensus == "FDM"
    assert len(e.matched_configurations) == count


def test_cross_mode_ambiguity_cannot_become_mode_consensus(monkeypatch):
    import alma_duplicate.queue_mode as module

    base = derive_queue_mode(12, "DOUBLE", 1875, 31.25).matched_configurations[0]
    with monkeypatch.context() as patch:
        patch.setattr(
            module,
            "configurations",
            lambda cycle: (
                base,
                replace(base, configuration_id="CONFLICT", mode="FDM"),
            ),
        )
        derive_queue_mode.cache_clear()
        e = derive_queue_mode(12, "DOUBLE", 1875, 31.25)
        assert e.unique_configuration_mode == e.conditional_mode_consensus == "UNKNOWN"
        assert e.compatible_modes == ("FDM", "TDM")
    derive_queue_mode.cache_clear()


@pytest.mark.parametrize(
    "cycle,pol,bw,res,reason",
    [
        (10, "DOUBLE", 1875, 31.25, "UNSUPPORTED_CYCLE"),
        (None, "DOUBLE", 1875, 31.25, "UNSUPPORTED_CYCLE"),
        (12, "", 1875, 31.25, "UNKNOWN_OR_UNSUPPORTED_POLARIZATION"),
        (12, "SINGLE", 1875, 31.25, "UNKNOWN_OR_UNSUPPORTED_POLARIZATION"),
        (12, "DOUBLE", None, 31.25, "INCOMPLETE_EVIDENCE"),
        (12, "DOUBLE", 1875, None, "INCOMPLETE_EVIDENCE"),
        (12, "DOUBLE", -1, 31.25, "INVALID_BANDWIDTH"),
        (12, "DOUBLE", float("nan"), 31.25, "INVALID_BANDWIDTH"),
        (12, "DOUBLE", 1875, float("inf"), "INVALID_RESOLUTION"),
        (12, "DOUBLE", 1875, 0, "INVALID_RESOLUTION"),
        (12, "DOUBLE", 1900, 31.25, "UNSUPPORTED_BANDWIDTH"),
        (12, "DOUBLE", 1875, 30, "NONSTANDARD_RESOLUTION"),
        (12, "DOUBLE", 62.5, 100, "NONSTANDARD_RESOLUTION"),
    ],
)
def test_fail_closed(cycle, pol, bw, res, reason):
    e = derive_queue_mode(cycle, pol, bw, res)
    assert e.unique_configuration_mode == e.conditional_mode_consensus == "UNKNOWN"
    assert e.configuration_reason == reason
    assert e.matched_configurations == ()


def test_no_nearest_neighbor_or_excessive_rounding():
    e = derive_queue_mode(12, "DOUBLE", 1875, 7.81225)
    assert e.configuration_reason == "NONSTANDARD_RESOLUTION"
    assert (
        derive_queue_mode(12, "DOUBLE", 1875, 7.8125).conditional_mode_consensus
        == "FDM"
    )


@pytest.mark.parametrize(
    "code,cycle",
    [
        ("2024.1.00001.S", 11),
        ("2024.A.00044.T", 11),
        ("2025.1.00383.L", 12),
        ("2026.1.00001.S", 13),
        ("2023.1.00001.S", None),
        ("2025-bad", None),
    ],
)
def test_cycle_is_submission_year_not_snapshot_year(code, cycle):
    assert project_cycle(code) == cycle


def test_catalog_has_unique_ids_and_respects_scope():
    for cycle in (11, 12, 13):
        rows = configurations(cycle)
        assert len({c.configuration_id for c in rows}) == len(rows)
        assert {c.cycle for c in rows} == {cycle}
        assert all(
            c.polarization == "DOUBLE"
            and c.bandwidth_mhz <= 1000
            and c.resource_fraction == 1
            for c in rows
            if c.quantization == "4X4"
        )
        assert all(c.resource_fraction == 1 for c in rows if c.bandwidth_mhz == 1875)
        assert all(
            c.resource_fraction == 1
            for c in rows
            if c.polarization == "FULL" and c.bandwidth_mhz == 500
        )
    assert configurations(10) == ()
