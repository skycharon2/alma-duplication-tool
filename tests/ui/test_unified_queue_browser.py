"""Browser dispatch retains all supported Queue geometries from one snapshot."""
import re
from unittest.mock import Mock

import pytest

from alma_duplicate.ui import create_app
from tests.integration.test_candidate_search import queue_rows
from tests.integration.test_queue_custom_science import candidate as custom
from tests.integration.test_queue_rectangle_science import candidate as rectangle
from tests.ui.test_queue_custom_mosaic import form, submit
from tests.unit.test_queue_csv_parser import _records, _render


@pytest.mark.parametrize('geometry', ['MOSAIC', 'SINGLE_POINTING'])
def test_mixed_queue_and_both_intents(tmp_path, monkeypatch, geometry):
    from alma_duplicate.ui.runs import QueueCsvClient
    rows = [dict(zip(r.raw_row.declared_columns, r.raw_row.raw_values))
            for parsed in (custom(), rectangle()) for r in parsed.row_inputs]
    parsed = queue_rows(*rows, {'Mosaic': ''})
    path = tmp_path / 'queue.csv'
    path.write_bytes(_render(_records()[:41] + [list(r.raw_values) for r in parsed.raw_rows]))
    loader = Mock(return_value=parsed)
    monkeypatch.setattr(QueueCsvClient, 'parse_bytes', loader)
    app = create_app(dict(TESTING=True, REPORT_DIRECTORY=None, OFFLINE_QUEUE_CSV=str(path),
        MANAGED_QUEUE_ROOT=None, OFFLINE_ARCHIVE_REPLAY=None, LIVE_ARCHIVE=False, LIVE_AQ=False))
    try:
        client = app.test_client()
        data = form(intents=('LINE', 'CONTINUUM'))
        if geometry == 'MOSAIC':
            response = submit(client, data)
        else:
            data['geometry'] = geometry
            data.update(dict(ra='150', dec='-30', action='assess'))
            response = client.post('/proposed', data=data)
        assert response.status_code == 303, response.text
        page = client.get(response.location)
        assert page.status_code == 200
        sibling = re.search(r'href="([^"]+)">Continuum</a>', page.text).group(1)
        for url in (response.location, sibling):
            report = client.get(url + '/download/report').json
            if geometry == 'SINGLE_POINTING':
                assert report['context_evaluations']
                report = report['queue_geometry_assessment']
                expected = {'CUSTOM', 'RECTANGLE'}
            else:
                expected = {'CUSTOM_POINTING', 'RECTANGULAR_MOSAIC', 'SINGLE_FIELD'}
            assert set(report['geometry_reports']) == expected
            assert all(g['candidates'] for g in report['geometry_reports'].values())
            assert report['search_completeness'] == 'NOT_ESTABLISHED'
            assert client.get(url).status_code == 200
        loader.assert_called_once()
    finally:
        app.extensions['assessment_runs'].close()


def test_mosaic_keeps_queue_when_archive_not_configured(tmp_path):
    path = tmp_path / 'queue.csv'
    parsed = custom()
    path.write_bytes(_render(_records()[:41] + [list(r.raw_values) for r in parsed.raw_rows]))
    app = create_app(dict(TESTING=True, REPORT_DIRECTORY=None, OFFLINE_QUEUE_CSV=str(path),
        MANAGED_QUEUE_ROOT=None, OFFLINE_ARCHIVE_REPLAY=None, LIVE_ARCHIVE=False, LIVE_AQ=False))
    try:
        client = app.test_client()
        data = form()
        data.setlist('sources', ['ARCHIVE', 'QUEUE'])
        response = submit(client, data)
        assert response.status_code == 303
        report = client.get(response.location + '/download/report').json
        assert report['geometry_reports']['CUSTOM_POINTING']['candidates']
        page = client.get(response.location).text
        assert 'Incomplete assessment' in page and 'Continuum · ARCHIVE' in page
    finally:
        app.extensions['assessment_runs'].close()


def test_snapshot_error_is_cached():
    from alma_duplicate.ui.queue_browser import memoized_loader
    loader = Mock(side_effect=OSError('unavailable snapshot'))
    pinned = memoized_loader(loader)
    for _ in range(2):
        with pytest.raises(OSError, match='unavailable snapshot'):
            pinned()
    loader.assert_called_once_with()


def test_queue_report_reads_only_matching_page(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from alma_duplicate.ui.run_store import RunStore
    store = RunStore(directory=tmp_path)
    candidates = [dict(candidate_id=str(i), science={'branches': [{'truth': truth}]})
                  for i, truth in enumerate(['TRUE'] * 45 + ['UNKNOWN'] * 30 + ['FALSE'] * 25)]
    document = dict(schema_version='queue_mosaic_assessment_1', assessment_status='COMPLETED',
                    duplication_status='NO_SEARCH_WIDE_ABSENCE_CLAIM', proposed={'source_name': 'test'},
                    geometry_reports={'CUSTOM_POINTING': {'candidates': candidates}})
    try:
        run_id = store.add({}, SimpleNamespace(document=document, status='COMPLETED'))
        original = Path.read_bytes
        def bounded(path):
            assert path.name != 'report.json', 'Report views must not read the full scientific report'
            return original(path)
        monkeypatch.setattr(Path, 'read_bytes', bounded)
        for page, expected in [(1, 20), (2, 20), (3, 5)]:
            result = store.page(run_id, page)
            shown = result['document']['geometry_reports']['CUSTOM_POINTING']['candidates']
            assert len(shown) == expected
            assert all(c['science']['branches'][0]['truth'] == 'TRUE' for c in shown)
            assert result['visible_count'] == 45
            assert result['pages'] == 3
        review = store.queue_page(run_id, 1, 'review')
        assert review['visible_count'] == 30
        assert review['document']['candidate_counts'] == {'matching': 45, 'review': 30, 'not_met': 25}
        projection = json.loads(next(store.directory.glob('*/view.json')).read_text())
        assert 'candidates' not in str(projection['document'])
    finally:
        store.close()


def test_legacy_scope_diagnostics_superseded_only_after_geometry_completion():
    from alma_duplicate.ui.report_view import attention_groups, report_summary
    context = dict(context_id='row-1', reference={'source': 'QUEUE'},
        criteria=[dict(details=[['queue_geometry', 'CUSTOM_POINTING']])],
        branches=[dict(branch='CONTINUUM', status='INDETERMINATE')])
    document = dict(context_evaluations=[context], request={},
                    queue_geometry_assessment={'assessment_status': 'COMPLETED'})
    inspection = {'gap_occurrences': [dict(context_id='row-1',
        code='QUEUE_GEOMETRY_UNSUPPORTED', category='SCOPE_UNSUPPORTED')]}
    assert attention_groups(document, inspection) == []
    assert report_summary(document)['total'] == 0
    document['queue_geometry_assessment']['assessment_status'] = 'SOURCES_UNAVAILABLE'
    assert attention_groups(document, inspection)
    assert report_summary(document)['total'] == 1
