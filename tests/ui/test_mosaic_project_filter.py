"""P0.6: project filter identity is recorded, candidate-bound, and read-only."""
from pathlib import Path

from alma_duplicate.ui.mosaic_visualization import _archive_project, queue_rows
from tests.ui.test_queue_geometry_visualization import sample


def _entry(projects=('2025.1.00123.S',)):
    return {'candidate': {'member_ous_uid': 'uid://member/1', 'source_name': 'NGC253'},
            'identity': {'projects': list(projects)}}


def test_archive_project_falls_back_only_to_unique_member_target_metadata():
    assert _archive_project(_entry(), {}) == '2025.1.00123.S'
    assert _archive_project(_entry(('A', 'B')), {}) is None
    assert _archive_project(_entry(()), {}) is None


def test_archive_context_project_must_match_member_target_and_recorded_metadata():
    ctx = {'display_identity': {'Project': 'B', 'Member OUS': 'uid://member/1',
                                'Target': 'NGC253'}}
    assert _archive_project(_entry(('A', 'B')), ctx) == 'B'
    assert _archive_project(_entry(('A',)), ctx) is None
    ctx['display_identity']['Target'] = 'Unrelated target'
    assert _archive_project(_entry(('A', 'B')), ctx) is None


def test_queue_project_comes_from_saved_configuration_group():
    page = sample()
    candidate = page['document']['geometry_reports']['RECTANGLE']['candidates'][0]
    candidate.setdefault('group', {})['project_code'] = '2026.1.45678.S'
    row = next(queue_rows(page))
    assert row['project'] == '2026.1.45678.S'
    assert row['source'] == 'Queue'


def test_mosaic_template_exposes_project_filter_without_renaming_source():
    path = (Path(__file__).resolve().parents[2] /
            'src/alma_duplicate/ui/templates/mosaic_visualization.html')
    html = path.read_text()
    assert "('project','Project')" in html
    assert "data-project=\"{{ row.project or '' }}\"" in html
    assert 'data-source="{{ row.source }}"' in html
