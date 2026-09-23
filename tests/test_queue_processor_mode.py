"""Independent boundary checks for the conditional processor experiment."""
import pytest
from alma_duplicate.queue_processor_mode import configurations, consensus, evaluate, match

@pytest.mark.parametrize("cycle", [11, 12, 13])
def test_single_polarization(cycle):
    assert evaluate(cycle, "SINGLE", 1875., 0.48828125)["known_profile_consensus"] == "FDM"
    assert evaluate(cycle, "SINGLE", 1875., 15.625)["known_profile_consensus"] == "TDM"
    assert evaluate(cycle, "SINGLE", 1875., 15.625)["formal_mode"] == "UNKNOWN"


def test_non_hanning_reference():
    rows = match(12, "DOUBLE", 1875., 2000 / 4096 * 1.207)
    assert rows and {c.weighting for c in rows} == {"UNIFORM"}


def test_export_profile_is_opt_in():
    assert not match(12, "DOUBLE", 1875., 7.81201171875)
    assert match(12, "DOUBLE", 1875., 7.81201171875, include_export_compatibility=True)


def test_full_tp_cannot_be_silently_dropped():
    value = evaluate(12, "FULL", 1875., 1.953125)
    assert value["known_profile_consensus"] == "FDM"
    assert value["conditional_processor_consensus"] == "UNKNOWN"
    assert value["reasons"] == ["FULL_POLARIZATION_TP_UNSUPPORTED"]


def test_4x4_mapping_has_distinct_bandwidth():
    value = evaluate(12, "DOUBLE", 250., 0.564453125)
    mappings = [m for m in value["tps_mappings"] if "4X4" in m["blc_configuration_id"]]
    assert mappings and all(m["counterpart_nominal_bandwidth_mhz"] == 1000 for m in mappings)
    assert all(m["counterpart_resolution_mhz"] == 0.564453125 for m in mappings)
    assert all(m["native_mode"] is None for m in mappings)


def test_unmapped_family_blocks_consensus():
    value = evaluate(12, "DOUBLE", 1000., 2.2578125)
    assert value["known_profile_consensus"] == "FDM"
    assert value["conditional_processor_consensus"] == "UNKNOWN"
    assert "TP_COUNTERPART_EXCEEDS_SUPPORTED_BASEBAND" in value["reasons"]
    assert evaluate(12, "DOUBLE", 1000., 2.2578125, require_tp=False)["conditional_processor_consensus"] == "FDM"


@pytest.mark.parametrize("cycle,pol,bw,res", [(10,"DOUBLE",1875,1), (12,"OTHER",1875,1), (12,"DOUBLE",float("nan"),1), (12,"DOUBLE",1875,0)])
def test_invalid_or_unsupported(cycle, pol, bw, res):
    assert evaluate(cycle, pol, bw, res)["conditional_processor_consensus"] == "UNKNOWN"


def test_mode_agreement_not_configuration_uniqueness():
    assert consensus(["FDM", "FDM"]) == "FDM"
    assert consensus(["FDM", "TDM"]) == "UNKNOWN"
    assert consensus([]) == "UNKNOWN"
    assert len(match(12, "DOUBLE", 62.5, .06103515625)) > 1
    assert evaluate(12, "DOUBLE", 62.5, .06103515625)["known_profile_consensus"] == "FDM"


def test_catalog_ids_unique_and_no_false_completion():
    rows = configurations(12)
    assert len({c.configuration_id for c in rows}) == len(rows)
    assert evaluate(12, "DOUBLE", 1875, .9765625)["enumeration_complete"] is False
