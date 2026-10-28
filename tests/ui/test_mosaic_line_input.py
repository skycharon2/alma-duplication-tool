"""Normal form adaptation keeps explicit requirements and linked evidence distinct."""
from copy import deepcopy

import pytest

from alma_duplicate.ui.mosaic_line_input import submitted_document, is_mosaic_line
from alma_duplicate.ui.proposed import build_document
from tests.ui.test_mosaic_execution import form, ROW


def document():
    values = form() | {'intents': ['LINE'], 'sources': ['ARCHIVE']}
    return build_document(values, [ROW])[0]


def test_bandwidth_is_linked_evidence_without_a_second_requirement():
    raw = document()
    raw['request']['spectral_windows'][0].update(
        bandwidth={'value': '1875', 'unit': 'MHz'}, bandwidth_kind='USABLE')
    before = deepcopy(raw)
    converted = submitted_document(raw)['request']
    assert raw == before
    assert len(converted['line_requirements']) == len(converted['physical_spw_evidence']) == 1
    assert converted['physical_spw_evidence'][0]['linked_line_requirement_id'] == 'line-0'


def test_incomplete_added_requirement_cannot_be_filtered_out():
    raw = document()
    other = deepcopy(raw['request']['spectral_windows'][0])
    other['window_id'] = 'second'
    raw['request']['spectral_windows'].append(other)
    with pytest.raises(ValueError, match='one sensitivity'):
        submitted_document(raw)


@pytest.mark.parametrize('change', [
    {'intents': ['LINE', 'CONTINUUM']}, {'geometry': 'SINGLE_POINTING'},
])
def test_unmigrated_scopes_are_not_selected(change):
    raw = document()
    raw['request'].update(change)
    assert not is_mosaic_line(raw)
