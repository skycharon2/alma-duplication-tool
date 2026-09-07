from dataclasses import replace
from unittest.mock import patch

import pytest

from alma_duplicate.domain import SupportComponentRef
from alma_duplicate.domain.reconstruction import ArchiveRowInput
from alma_duplicate.parsers.frequency_support import parse_frequency_support
from alma_duplicate.reconstruction import reconstruct_archive_rows


SUPPORT = (
    "  [99..101GHz, 1MHz, 1mJy/beam@10km/s, "
    "0.2mJy/beam@native, XX YY]  "
)


def row(identity, support, obs_id="broken"):
    return ArchiveRowInput(
        identity, "uid://A001/X1/X1", "uid://A002/X1/X1",
        obs_id, 100.0, support,
    )


@pytest.mark.parametrize("support", [
    SUPPORT, SUPPORT.encode(), None, "  ", "unknown grammar",
    "[99..101GHz, 1MHz, mystery, XX YY]",
    "[101..99GHz, 1MHz, XX YY]",
    "{100.00GHz,2000000kHz,1mJy/beam@native, XX YY}",
])
def test_full_parser_result_survives_unsafe_identifier(support):
    expected = parse_frequency_support(support)
    with patch(
        "alma_duplicate.reconstruction.parse_frequency_support",
        wraps=parse_frequency_support,
    ) as parser:
        batch = reconstruct_archive_rows([row("raw-1", support)])
    parser.assert_called_once_with(support)
    evidence = batch.frequency_support_evidence[0]
    assert evidence.raw_row_id == "raw-1"
    assert evidence.parse_result == expected
    assert evidence.parse_result.raw_value == support
    assert not batch.row_reconstructions[0].is_linked
    assert batch.support_mappings[0].component_ref is None
    assert batch.support_mappings[0].grammar_family == expected.grammar_family


def test_mapping_reuses_saved_object_and_references_resolve():
    obs_id = "uid://A001/X1/X1.source.Target.spw.0"
    rows = [row("a", SUPPORT, obs_id), row("b", SUPPORT, obs_id)]
    with patch(
        "alma_duplicate.reconstruction.parse_frequency_support",
        wraps=parse_frequency_support,
    ) as parser:
        batch = reconstruct_archive_rows(rows)
    assert parser.call_count == 2
    for evidence, mapping in zip(
        batch.frequency_support_evidence, batch.support_mappings, strict=True
    ):
        assert mapping.is_assigned
        assert mapping.candidate_count == len(mapping.candidate_refs) == 1
        reference = mapping.component_ref
        assert reference is not None
        assert evidence.resolve(reference) is evidence.parse_result.components[0]
        with pytest.raises(ValueError):
            evidence.resolve(replace(reference, raw_row_id="other"))
        with pytest.raises(ValueError):
            evidence.resolve(replace(reference, parser_version="other"))
        with pytest.raises(KeyError):
            evidence.resolve(replace(reference, component_index=999))
    assert batch.support_mappings[0].component_ref != (
        batch.support_mappings[1].component_ref
    )
    assert reconstruct_archive_rows(reversed(rows)) == batch


def test_all_ambiguous_references_resolve_to_saved_components():
    support = SUPPORT + " U " + SUPPORT
    batch = reconstruct_archive_rows([
        row("raw", support, "uid://A001/X1/X1.source.Target.spw.0")
    ])
    evidence = batch.frequency_support_evidence[0]
    mapping = batch.support_mappings[0]
    assert mapping.component_ref is None
    assert mapping.candidate_count == len(mapping.candidate_refs) == 2
    assert tuple(evidence.resolve(ref) for ref in mapping.candidate_refs) == (
        evidence.parse_result.components
    )
    assert all(isinstance(ref, SupportComponentRef) for ref in mapping.candidate_refs)


def test_empty_batch_has_empty_evidence():
    assert reconstruct_archive_rows([]).frequency_support_evidence == ()
