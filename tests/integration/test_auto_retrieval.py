"""Bounded automatic retrieval and legacy requests, without external access."""
from dataclasses import replace

import pytest

from alma_duplicate.assessment import ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation
from alma_duplicate.auto_retrieval import automatic_radius, automatic_scope
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.clients.archive_queries import build_count_adql, build_retrieval_adql, normalize_query_parameters
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import build_search_plan
from tests.integration.test_confirmed_continuum import payload
from tests.integration.test_live_aq_assessment import tap_rows, fetcher, acquisition
from tests.integration.test_search_plan_spatial import queue


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, 'request', lambda *a, **k: pytest.fail('network'))


def auto_payload(sources=('ARCHIVE',), limit=1):
    data = payload()
    data['search_options'] = {'radius_mode': 'AUTO', 'sources': list(sources), 'result_limit': limit}
    return data


def validate(data):
    return validate_proposed_observation(data["request"], data["search_options"])


def bind(source, query):
    """Fake TAP echoes the actual requested query, as the real client does."""
    return replace(source, provenance=replace(source.provenance,
        normalized_parameters=normalize_query_parameters(query), count_adql=build_count_adql(query),
        retrieval_adql=build_retrieval_adql(query), projection=None))


@pytest.mark.parametrize('frequency', [35., 40., 100., 230., 950.])
@pytest.mark.parametrize('diameter', [7., 12.])
def test_envelope_covers_supported_candidate_half_power_radii(frequency, diameter):
    radius = automatic_radius().value
    assert radius >= primary_beam_fwhm_deg(frequency, diameter) / 2
    assert radius == pytest.approx(primary_beam_fwhm_deg(35., 7.) / 2, abs=1e-10)
    assert 'ARCHIVE_UNKNOWN_OR_LOWER_FREQUENCY_OUTSIDE_CONE_NOT_COVERED' in automatic_scope()['limitations']


@pytest.mark.parametrize('mode', [None, '', 'auto', [], {}, 1, True])
def test_invalid_mode_is_diagnosed(mode):
    data = auto_payload()
    data['search_options']['radius_mode'] = mode
    result = validate(data)
    assert not result.is_valid
    assert 'INVALID_RADIUS_MODE' in {issue.code for issue in result.errors}


def test_auto_requires_no_scientific_frequency_but_does_not_invent_it():
    data = auto_payload()
    data['request'].pop('representative_frequency', None)
    data['request']['spectral_windows'] = []
    data['request']['sensitivities'] = []
    v = validate(data)
    assert v.is_valid and v.can_search
    assert v.request.representative_frequency is None
    assert 'radius' not in v.raw_search_options
    assert v.search_options.radius == automatic_radius()


def test_conflicting_radius_and_legacy_compatibility():
    data = auto_payload()
    data['search_options']['radius'] = {'value': 30, 'unit': 'arcsec'}
    v = validate(data)
    assert not v.is_valid and 'AUTO_RADIUS_CONFLICT' in {i.code for i in v.errors}
    del data['search_options']['radius_mode']
    legacy = validate(data)
    assert legacy.is_valid and legacy.search_options.radius.value == pytest.approx(30 / 3600)
    plan = build_search_plan(legacy)
    assert plan.version == '1' and plan.retrieval_policy is None
    assert plan.for_source('ARCHIVE').archive_query.spatial_strategy == 'REGION'
    del data['search_options']['radius']
    assert not validate(data).can_search


@pytest.mark.parametrize('options', [AssessmentOptions(queue_candidate_beam=True),
                                     AssessmentOptions(beam_decision_ref='legacy')])
def test_strategy_conflict_fails_before_source_access(options):
    with pytest.raises(ValueError, match='AUTO'):
        assess_observation(**auto_payload(), options=options,
            sources=AssessmentSources('LIVE', lambda: pytest.fail('TAP created')))


def test_auto_tap_aq_all_members_policy_and_display_independence():
    source, members = tap_rows()
    calls = []
    class Tap:
        def search(self, query):
            calls.append(query)
            assert query.spatial_strategy == 'CENTER'
            assert 's_region' not in build_count_adql(query)
            assert query.radius_deg == automatic_radius().value
            return bind(source, query)
    fetch = fetcher(members)
    def aq(requested):
        assert len(calls) == 1 and requested == members
        return fetch(requested)
    data = auto_payload()
    result = assess_observation(**data, sources=AssessmentSources('LIVE', lambda: ArchiveInput(Tap()),
                                                                archive_array_fetcher=aq))
    doc = result.document
    assert result.status == 'COMPLETED'
    assert len(doc['context_evaluations']) == 3
    assert doc['evaluation_scope']['shown_candidates'] == 1
    assert acquisition(result)['status'] == 'COMPLETED'
    assert doc['plan']['retrieval_policy'] == automatic_scope()
    assert doc['request']['search_options']['radius']['value'] == automatic_radius().value
    assert 'radius' not in doc['request']['raw_search_options']
    assert all(c['array_evidence']['diameters_m'] == [7.] for c in doc['context_evaluations'])
    assert 'REQUESTED_FILTERS_NOT_FULLY_EVALUATED' not in {g['code'] for g in inspect_report(doc)['gap_occurrences']}
    data['search_options']['result_limit'] = 100
    data['request']['representative_frequency']['value'] = 100
    query = build_search_plan(validate(data)).for_source('ARCHIVE').archive_query
    assert query == calls[0]


@pytest.mark.parametrize('status', [ArchiveQueryStatus.OVERFLOW, ArchiveQueryStatus.COUNT_MISMATCH])
def test_incomplete_tap_never_retries_or_shrinks_radius(status):
    source, _ = tap_rows()
    calls = []
    class Tap:
        def search(self, query):
            calls.append(query)
            return replace(bind(source, query), status=status)
    result = assess_observation(**auto_payload(), sources=AssessmentSources('LIVE', lambda: ArchiveInput(Tap()),
        archive_array_fetcher=lambda _: pytest.fail('AQ must skip incomplete TAP')))
    assert len(calls) == 1 and calls[0].radius_deg == automatic_radius().value
    assert result.status == 'SOURCES_UNAVAILABLE'
    assert acquisition(result)['reason'] == 'TAP_NOT_COMPLETED'
    assert result.document['plan']['retrieval_policy'] == automatic_scope()
    assert result.document['assessment'] == 'NOT_AGGREGATED'


@pytest.mark.parametrize('ra', ['0', '180'])
def test_queue_all_supplied_contexts_survive_distance_and_unknown_frame(ra):
    source, _ = queue(RA=ra)
    v = validate(auto_payload(('QUEUE',)))
    result = search_candidates(v, queue_result=source)
    assert result.queue.status == 'COMPLETED'
    assert result.queue.rows and len(result.queue.retained_rows) == len(result.queue.rows)
    assert all(not row.filters for row in result.queue.rows)
    assert result.queue.plan.spatial_operation == 'AUTO_QUEUE_ALL_ROWS'
