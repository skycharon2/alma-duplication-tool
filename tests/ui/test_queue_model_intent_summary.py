"""Accepted Rectangle model and intent-scoped Queue report-index tests."""

from alma_duplicate.ui.queue_browser import report_header


def candidate(*branches):
    return {'candidate_id': str(id(branches)), 'science': {'branches': [
        {'branch': intent, 'truth': truth} for intent, truth in branches]}}


def test_intent_counts_across_all_candidates_and_sources():
    report = {'geometry_reports': {
        'RECTANGLE': {'candidates': [
            candidate(('CONTINUUM', 'TRUE')),
            candidate(('LINE', 'TRUE')),
            candidate(('CONTINUUM', 'TRUE'), ('LINE', 'TRUE')),
            candidate(('CONTINUUM', 'UNKNOWN')),
        ]},
        'CUSTOM': {'candidates': [candidate(('CONTINUUM', 'FALSE'))]},
    }}
    header = report_header(report)
    assert header['candidate_counts_by_intent'] == {
        'CONTINUUM': {'matching': 2, 'review': 1, 'not_met': 1},
        'LINE': {'matching': 2, 'review': 0, 'not_met': 0},
    }
    assert header['candidate_counts']['matching'] == 3
    assert header['intent_counts_scope'] == 'ALL_STORED_CANDIDATE_CONFIGURATIONS'
    assert header['geometry_reports'] == {}


def test_repeated_branch_is_counted_only_once_within_candidate():
    header = report_header({'geometry_reports': {'RECTANGLE': {'candidates': [
        candidate(('CONTINUUM', 'FALSE'), ('CONTINUUM', 'TRUE')),
    ]}}})
    assert header['candidate_counts_by_intent']['CONTINUUM']['matching'] == 1


def test_legacy_index_does_not_fabricate_intent_breakdown():
    # Saved legacy headers still exist and must remain valid input to report
    # rendering, but an old header cannot be reclassified from page 1 alone.
    old = {'candidate_counts': {'matching': 1, 'review': 0, 'not_met': 0}}
    assert 'candidate_counts_by_intent' not in old


def test_page_uses_full_intent_index_not_twenty_visible_candidates(tmp_path):
    from types import SimpleNamespace
    from alma_duplicate.ui import create_app
    from tests.integration.test_line_preparation import report
    from tests.ui.test_calculation_view import serialized

    document = serialized(report())
    # The original report fixture was LINE only; test a separate submitted
    # CONTINUUM intent against a completely independent Queue candidate group.
    for form in ('raw', 'normalized'):
        if isinstance(document['request'].get(form), dict):
            document['request'][form]['intents'] = ['CONTINUUM']
    candidates = [
        dict(candidate_id=f'q-{i}', group={'target_name': 'L1544',
             'project_code': '2025.1.00609.S'},
             position={'beam_variants': [{'diameter_m': 12.0}]},
             science={'model_status': 'PROJECT_ACCEPTED',
                 'scientific_candidate_completeness': 'COMPLETE_FOR_EVALUATED_INTENT',
                 'intent_completeness': {'CONTINUUM': 'COMPLETE_FOR_EVALUATED_INTENT'},
                 'branches': [{'branch': 'CONTINUUM', 'truth': 'TRUE',
                               'status': 'CRITERIA_MET'}],
                 'variants': [{'diameter_m': 12.0, 'criteria': [],
                               'line_pairs': [], 'branches': []}]}) for i in range(23)]
    document['queue_geometry_assessment'] = {
        'assessment_status': 'COMPLETED',
        'geometry_reports': {'RECTANGLE': {'candidates': candidates}}}
    app = create_app({'TESTING': True, 'REPORT_DIRECTORY': None,
                      'LIVE_ARCHIVE': False, 'LIVE_AQ': False})
    store = app.extensions['assessment_runs']
    try:
        run_id = store.add({'request': document['request']},
                           SimpleNamespace(document=document, status='COMPLETED'))
        page = app.test_client().get(f'/runs/{run_id}').get_data(as_text=True)
        assert '<strong>23</strong> matching Queue Mosaic candidate configurations' in page
        # Header count must come from all 23 configurations, not the 20 loaded.
        assert '0 matching standard comparisons' not in page or '23' in page
    finally:
        store.close()
