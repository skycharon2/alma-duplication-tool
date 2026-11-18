"""Overlapping support must be bound by explicit row edges, never nearest centre."""
from dataclasses import replace
from pathlib import Path

import pytest
from astropy.io.votable import parse_single_table

from alma_duplicate.clients.archive_adapter import _spectral_bounds, run_archive_pipeline
from alma_duplicate.domain.reconstruction import SupportMappingStatus, SupportMappingMethod
from alma_duplicate.reconstruction import reconstruct_archive_rows
from tests.unit.test_reconstruction import _row
from tests.integration.test_archive_pipeline_fixture import _complete_query_result
from alma_duplicate.clients.archive_contract import TapFieldMetadata

FIXTURE = Path(__file__).parents[1] / 'fixtures/archive_spw_overlap/m33.xml'


def captured():
    table = parse_single_table(FIXTURE)
    fields = tuple(TapFieldMetadata(f.name, f.datatype, f.arraysize, str(f.unit) if f.unit else None,
                                   f.ucd, f.utype, f.xtype, f.description) for f in table.fields)
    rows = [dict(zip(table.to_table().colnames, row)) for row in table.to_table()]
    return rows, fields


def test_real_overlapping_spws_through_adapter_and_reconstruction():
    rows, fields = captured()
    base = _complete_query_result()
    metadata = tuple(f for f in base.field_metadata if f.name not in {f.name for f in fields}) + fields
    result = replace(base, rows=tuple(dict(base.rows[0]) | row | {
        'member_ous_uid': 'uid://A001/X3833/X1121',
        'asdm_uid': 'uid://A002/X13c84cf/X232f9'} for row in rows), field_metadata=metadata)
    pipeline = run_archive_pipeline(result)
    mapping = pipeline.reconstruction.support_mappings
    assert [m.component_index for m in mapping] == [3, 1, 4, 2]
    assert all(m.status == SupportMappingStatus.ASSIGNED for m in mapping)
    assert [m.method for m in mapping] == [SupportMappingMethod.BRACKET_ROW_BOUNDS,
        SupportMappingMethod.BRACKET_ROW_BOUNDS, SupportMappingMethod.BRACKET_INTERVAL_CONTAINMENT,
        SupportMappingMethod.BRACKET_ROW_BOUNDS]
    assert all(m.component_ref is not None and m.candidate_count == 1 for m in mapping)
    # Exercise the shared JSON -> visualization path, not a separate UI mapping.
    import json
    from types import SimpleNamespace
    from alma_duplicate.clients.archive_client import ArchiveClient
    from alma_duplicate.clients.archive_contract import TapResponse
    from tests.fakes import FakeTapExecutor
    from tests.unit.test_archive_client import _count_response
    def search(spec):
        return ArchiveClient('https://example.invalid/tap', executor=FakeTapExecutor([
            _count_response(4), TapResponse(rows=result.rows, declared_columns=tuple(f.name for f in result.field_metadata),
                field_metadata=result.field_metadata, query_status_raw='OK')])).search(spec)
    from alma_duplicate.candidate_search import search_candidates
    from alma_duplicate.rules.evaluation import evaluate_candidate_search
    from alma_duplicate.reporting import report_document, report_json_text
    from alma_duplicate.ui.visualization import continuum_coverage
    from tests.integration.test_line_preparation import validate, payload
    request = payload()
    request["search_options"].update(radius={"value": 21.6, "unit": "arcsec"}, result_limit=100)
    document = json.loads(report_json_text(report_document(evaluate_candidate_search(
        search_candidates(validate(request), archive_client=SimpleNamespace(search=search))))))
    contexts = document['context_evaluations']
    assert len(contexts) == 4, document['sources']['ARCHIVE']['reasons']
    assert [(continuum_coverage(c)[0]['low'], continuum_coverage(c)[0]['high']) for c in contexts] == [
        (230.44, 230.91), (228.49, 230.48), (231.81, 232.27), (229.38, 231.36)]
    evidence = contexts[0]['spectral_display']['association_evidence']
    assert evidence['method'] == 'BRACKET_ROW_BOUNDS'
    assert evidence['row_bounds_ghz'] == pytest.approx((230.44209067100638,230.91056928718868))
    # Original descriptors, support text and row bounds remain available for audit.
    assert pipeline.prepared_rows[0].raw_row['em_min'] == rows[0]['em_min']


@pytest.mark.parametrize('unit', ['m', 'mm'])
def test_explicit_wavelength_units_convert(unit):
    rows, fields = captured()
    row = rows[0]
    factor = 1000 if unit == 'mm' else 1
    fields = tuple(replace(f, unit=unit) if f.name in {'em_min','em_max'} else f for f in fields)
    bounds = _spectral_bounds(dict(row, em_min=row['em_min']*factor, em_max=row['em_max']*factor), fields)
    assert bounds == pytest.approx((230.44209067100638, 230.91056928718868))


@pytest.mark.parametrize('bad', [None, 0, -1, float('nan'), float('inf'), True, '0.001'])
def test_invalid_edge_does_not_authorize_mapping(bad):
    rows, fields = captured()
    assert _spectral_bounds(dict(rows[0], em_min=bad), fields) is None


@pytest.mark.parametrize('unit', [None, 'GHz', 'invalid'])
def test_missing_or_non_wavelength_units_rejected(unit):
    rows, fields = captured()
    fields = tuple(replace(f, unit=unit) if f.name == 'em_min' else f for f in fields)
    assert _spectral_bounds(rows[0], fields) is None


def test_duplicate_metadata_and_reversed_edges_rejected():
    rows, fields = captured()
    assert _spectral_bounds(rows[0], fields + (next(f for f in fields if f.name == 'em_min'),)) is None
    assert _spectral_bounds(dict(rows[0], em_min=rows[0]['em_max'], em_max=rows[0]['em_min']), fields) is None


@pytest.mark.parametrize('bounds', [None, (99.8,100.2), (100.1,100.0), (float('nan'),100.1)])
def test_missing_conflicting_bounds_keep_original_ambiguity(bounds):
    row = _row(raw_row_id='x', source='s', spw=17, frequency_ghz=100.0,
               frequency_support='[99.90..100.10GHz,1MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY] U [99.95..100.05GHz,1MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY]')
    row = replace(row, spectral_bounds_ghz=bounds)
    m = reconstruct_archive_rows([row]).support_mappings[0]
    assert m.status == SupportMappingStatus.AMBIGUOUS_MULTIPLE_INTERVALS
    assert m.component_ref is None


def test_duplicate_intervals_are_not_tiebroken_by_spw_or_order():
    row = _row(raw_row_id='x', source='s', spw=1, frequency_ghz=100.0,
               frequency_support='[99.90..100.10GHz,1MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY] U [99.90..100.10GHz,2MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY]')
    m = reconstruct_archive_rows([replace(row, spectral_bounds_ghz=(99.9,100.1))]).support_mappings[0]
    assert m.status == SupportMappingStatus.AMBIGUOUS_MULTIPLE_INTERVALS


@pytest.mark.parametrize('edge,assigned', [(99.904999,True),(99.905001,False)])
def test_each_endpoint_rounding_quantum_is_respected(edge, assigned):
    row = _row(raw_row_id='x', source='s', spw=1, frequency_ghz=100.0,
               frequency_support='[99.90..100.10GHz,1MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY] U [99.95..100.05GHz,1MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY]')
    m = reconstruct_archive_rows([replace(row, spectral_bounds_ghz=(edge,100.1))]).support_mappings[0]
    assert m.is_assigned == assigned


@pytest.mark.parametrize('support,expected', [
    ('[99900..100100MHz,1MHz] U [99950..100050MHz,1MHz]', 1),
    ('[9.990e1..1.0010e2GHz,1MHz] U [9.995e1..1.0005e2GHz,1MHz]', 1),
    ('[99.95..100.05GHz,1MHz] U [99.90..100.10GHz,1MHz]', 2),
])
def test_units_exponents_and_support_order_preserve_physical_mapping(support, expected):
    support = support.replace('MHz]', 'MHz,1mJy/beam@10km/s,0.2mJy/beam@native,XX YY]')
    row = _row(raw_row_id='x', source='s', spw=999, frequency_ghz=100.0,
               frequency_support=support)
    mapping = reconstruct_archive_rows([replace(row, spectral_bounds_ghz=(99.9,100.1))]).support_mappings[0]
    assert mapping.component_index == expected
    assert mapping.method == SupportMappingMethod.BRACKET_ROW_BOUNDS
