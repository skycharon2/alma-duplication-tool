"""Default Mosaic report selection is positive-first and projection-only."""

from alma_duplicate.ui.mosaic_report_pages import mosaic_report_page
from alma_duplicate.ui.mosaic_report_view import mosaic_report_projection


def test_default_mosaic_view_loads_only_matching_identity():
    report = {
        'schema_version': 'archive_mosaic_backend_2',
        'proposed': {'source_name': 'Example', 'row_count': 3},
        'assessment_status': 'COMPLETED',
        'discovery': {'status': 'COMPLETED'},
        'candidates': [
            {'member_ous_uid': 'member-unknown', 'source_name': 'A', 'status': 'EVALUATED',
             'evaluation': {'contexts': [{'context_id': 'a', 'branches': [
                 {'branch': 'LINE', 'status': 'INDETERMINATE'}]}]}},
            {'member_ous_uid': 'member-met', 'source_name': 'B', 'status': 'EVALUATED',
             'evaluation': {'contexts': [{'context_id': 'b', 'branches': [
                 {'branch': 'LINE', 'status': 'CRITERIA_MET'}]}]}},
        ],
    }
    indexed = mosaic_report_projection(report)
    loaded = []
    def load(index):
        loaded.append(index)
        return report['candidates'][index]

    default = mosaic_report_page(indexed, 1, 'matches', load)
    assert default['result_view'] == 'matching'
    assert default['visible_count'] == 1
    assert loaded == [1]
    assert default['candidate_entries'][0]['candidate']['source_name'] == 'B'
    assert indexed['candidate_count'] == 2
    assert len(report['candidates']) == 2

    loaded.clear()
    full = mosaic_report_page(indexed, 1, 'all', load)
    assert full['visible_count'] == 2
    assert loaded == [0, 1]
