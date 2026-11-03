from unittest.mock import Mock

from alma_duplicate.assessment import AssessmentSources, assess_observation
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_queue_custom_science import candidate as custom, request, pointings
from tests.integration.test_queue_rectangle_science import candidate as rectangle


def run(loader):
    req, payload = request()
    payload['search_options']['sources'] = ['QUEUE']
    return assess_observation(**payload, queue_mosaic=pointings(req),
                              sources=AssessmentSources(queue_loader=loader)).document


def test_one_snapshot_two_independent_assessments():
    rows = [dict(zip(r.raw_row.declared_columns, r.raw_row.raw_values))
            for parsed in (custom(), rectangle({'Ref.Frequency': '100'})) for r in parsed.row_inputs]
    loader = Mock(return_value=queue_rows(*rows, {'Mosaic': ''}))
    report = run(loader)
    loader.assert_called_once_with()
    inventory = report['inventory']
    assert inventory['unevaluated_rows'] == 0
    assert len(inventory['source_rows']) == len(rows) + 1
    for kind, truths in [('CUSTOM_POINTING', ['TRUE']), ('RECTANGULAR_MOSAIC', ['FALSE', 'FALSE'])]:
        result = report['geometry_reports'][kind]
        assert [c['science']['branches'][0]['truth'] for c in result['candidates']] == truths
        assert inventory['candidate_counts'][kind]['evaluated'] == len(truths)
    assert report['duplication_status'] == 'NO_SEARCH_WIDE_ABSENCE_CLAIM'


def test_missing_snapshot_has_unknown_inventory():
    report = run(None)
    assert report['inventory'] is None
    assert report['assessment_status'] == 'SOURCES_UNAVAILABLE'


def test_unresolved_galactic_candidate_retains_science_and_coverage_limitations():
    report = run(lambda: rectangle({'Mos. Coord.': 'galactic', 'Use TP?': 'True'}))
    inventory = report['inventory']
    assert inventory['candidate_counts']['RECTANGULAR_MOSAIC']['unresolved_by_intent'] == {'CONTINUUM': 2}
    for row in inventory['source_rows']:
        assert row['evaluated']
        assert 'GALACTIC_RECONSTRUCTION_UNSUPPORTED' in row['limitations']
        assert 'TP_COVERAGE_NOT_MODELLED' in row['limitations']
    assert report['search_completeness'] == 'NOT_ESTABLISHED'
