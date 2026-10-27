"""Mosaic report navigation is a read-only presentation over recorded decisions."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.mosaic_report_pages import mosaic_report_page
from alma_duplicate.ui.mosaic_report_view import mosaic_report_projection
from alma_duplicate.ui.run_store import RunStore


def _context(index, status):
    return {
        'context_id': f'context-{index}',
        'criteria': [{'criterion_id': 'POS-MOSAIC', 'outcome': 'SATISFIED',
                      'eligible_for_formal_aggregation': True}],
        'request_criteria': [], 'line_pairs': [],
        'branches': [{'branch': 'LINE', 'status': status}],
        'coverage': {'inside_count': 2, 'pointing_count': 3, 'outside_count': 1,
                     'boundary_count': 0, 'unknown_count': 0},
    }


def _document():
    buckets = ['CRITERIA_MET', 'CRITERIA_NOT_MET', 'INDETERMINATE']
    candidates = []
    for i in range(42):
        if i == 3:
            candidates.append({'member_ous_uid': 'uid://shared', 'source_name': 'target-3',
                               'status': 'INCOMPLETE', 'error': 'Archive response failed'})
        else:
            candidates.append({'member_ous_uid': 'uid://shared' if i in (0, 1) else f'uid://member/{i}',
                               'source_name': f'target-{i}', 'status': 'EVALUATED',
                               'evaluation': {'contexts': [_context(i, buckets[i % 3])]}})
    return {'schema_version': 'archive_mosaic_backend_2',
            'proposed': {'source_name': 'Mosaic test target', 'row_count': 3},
            'assessment_status': 'INCOMPLETE',
            'absence_interpretation': 'NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION',
            'discovery': {'status': 'COMPLETED'}, 'candidates': candidates}


def test_filtered_pages_preserve_original_indexes_and_member_boundaries():
    report = _document()
    before = deepcopy(report)
    projection = mosaic_report_projection(report)
    requested = []
    def read(index):
        requested.append(index)
        return report['candidates'][index]
    all_page = mosaic_report_page(projection, 1, 'matches', read)
    assert all_page['result_view'] == 'all'
    assert all_page['visible_count'] == 42
    assert all_page['pages'] == 3
    assert requested == list(range(20))
    assert [entry['candidate_index'] for entry in all_page['member_groups'][0]['entries']] == [0, 1, 3]
    assert all_page['member_groups'][0]['member_ous_uid'] == 'uid://shared'

    requested.clear()
    matched = mosaic_report_page(projection, 1, 'matching', read)
    expected = [i for i, s in enumerate(projection['candidate_summaries']) if s['bucket'] == 'MATCH']
    assert [item['candidate_index'] for item in matched['candidate_entries']] == expected[:20]
    assert requested == expected[:20]
    requested.clear()
    review = mosaic_report_page(projection, 1, 'review', read)
    assert review['visible_count'] == sum(1 for c in projection['candidate_summaries']
                                        if c['bucket'] in ('NEEDS_REVIEW', 'UNAVAILABLE'))
    assert 3 in requested
    assert all(projection['candidate_summaries'][i]['bucket'] in ('NEEDS_REVIEW', 'UNAVAILABLE')
               for i in requested)
    not_met = mosaic_report_page(projection, 1, 'not_met', lambda i: report['candidates'][i])
    assert all(item['summary']['bucket'] == 'NOT_MET' for item in not_met['candidate_entries'])
    assert report == before


@pytest.mark.parametrize('view', ['all', 'matching', 'review', 'not_met', 'matches'])
def test_empty_selection_is_one_empty_page(view):
    report = _document()
    report['candidates'] = []
    projection = mosaic_report_projection(report)
    page = mosaic_report_page(projection, 1, view, lambda i: pytest.fail('No candidate read'))
    assert page['pages'] == 1 and page['candidate_entries'] == []
    with pytest.raises(IndexError):
        mosaic_report_page(projection, 2, view, lambda i: None)


@pytest.mark.parametrize('page,view', [(0, 'all'), (1, 'bogus'), (1.0, 'all'), (-1, 'matching')])
def test_invalid_selection_is_rejected(page, view):
    with pytest.raises(ValueError):
        mosaic_report_page(mosaic_report_projection(_document()), page, view, lambda i: None)


def test_indexed_storage_filters_without_loading_unselected_candidate_bytes(tmp_path, monkeypatch):
    report = _document()
    original = deepcopy(report)
    store = RunStore(directory=tmp_path)
    try:
        request = {'request': {'geometry': 'MOSAIC'}}
        run_id = store.add(request, SimpleNamespace(document=report, status='COMPLETED'))
        assert report == original
        assert b''.join(store.open_download(run_id, 'report')) == report_json_text(report).encode()
        projection = json.loads((store._runs[run_id].directory / 'view.json').read_text())
        expected = [i for i, c in enumerate(projection['candidate_summaries']) if c['bucket'] == 'MATCH']
        original_loads = json.loads
        reads = []
        def count_reads(raw, *args, **kwargs):
            obj = original_loads(raw, *args, **kwargs)
            if isinstance(obj, dict) and 'member_ous_uid' in obj:
                reads.append(obj['source_name'])
            return obj
        monkeypatch.setattr(json, 'loads', count_reads)
        page = store.page(run_id, view='matching')
        assert page['result_view'] == 'matching'
        assert [e['candidate_index'] for e in page['candidate_entries']] == expected[:20]
        assert reads == [f'target-{i}' for i in expected[:20]]
        assert page['candidates'] == [report['candidates'][i] for i in expected[:20]]
        with pytest.raises(IndexError):
            store.page(run_id, page=999, view='matching')
        assert b''.join(store.open_download(run_id, 'report')) == report_json_text(report).encode()
    finally:
        store.close()


def test_template_parses_and_contains_hierarchical_sections():
    from jinja2 import Environment, FileSystemLoader
    template_dir = Path(__file__).resolve().parents[2] / 'src/alma_duplicate/ui/templates'
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    env.get_template('mosaic_report.html')


def test_hierarchical_template_renders_recorded_context_evidence():
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

    report = _document()
    first = report['candidates'][0]['evaluation']['contexts'][0]
    first['line_pairs'] = [{
        'status': 'CRITERIA_MET', 'criteria': [{
            'criterion_id': 'LINE-RMS', 'outcome': 'SATISFIED',
            'eligible_for_formal_aggregation': True, 'reasons': [],
        }],
    }]
    first['coverage']['points'] = [
        {'id': 'row-1', 'ra_deg': 11.8, 'dec_deg': -25.3, 'status': 'INSIDE'}
    ]
    projection = mosaic_report_projection(report)
    data = mosaic_report_page(projection, 1, 'matching', lambda i: report['candidates'][i])
    data.update(
        report_id='test-run', retention_hours=24,
        url_for=lambda endpoint, **params: '/' + endpoint,
        status_labels={'CRITERIA_MET': 'Meets these conditions',
                       'CRITERIA_NOT_MET': 'Does not meet these conditions',
                       'INDETERMINATE': 'Needs review'},
        display_number=str,
        criterion_view=lambda r: {'label': r['criterion_id'], 'proposed': None, 'candidate': None},
        criterion_status=lambda r: r['outcome'],
        criterion_explanation=lambda r: 'Stored result',
        pair_title=lambda r: 'candidate SPW 1',
    )
    template_dir = Path(__file__).resolve().parents[2] / 'src/alma_duplicate/ui/templates'
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block extra_head %}{% endblock %}'
                                 '{% block content %}{% endblock %}'}),
        FileSystemLoader(template_dir),
    ]), autoescape=True)
    rendered = env.get_template('mosaic_report.html').render(**data)
    for text in ('Mosaic assessment', 'Results in this search',
                 'Archive Member OUS:', 'Target: target-0', 'Context 1',
                 'Mosaic spatial coverage', 'Spectral line comparisons',
                 'row-1', 'candidate SPW 1', 'Download complete report JSON'):
        assert text in rendered
    assert 'uid://shared' in rendered
    assert 'SENSITIVE' not in rendered
