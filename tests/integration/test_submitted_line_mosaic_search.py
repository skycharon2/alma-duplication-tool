"""V2 discovery-to-evaluation integration using recorded spectral metadata."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.submitted_line_assessment import assess_submitted_line_mosaic_search_v2
from tests.integration.test_line_preparation import report
from tests.integration.test_submitted_line_assessment_step04c import _wire
from tests.integration.test_submitted_line_backend_acceptance import mosaic_case


@pytest.mark.parametrize("mode,expected", [
    ("complete", "COMPLETED"), ("partial", "INCOMPLETE"),
    ("overflow", "INCOMPLETE"), ("wrong_identity", "INCOMPLETE"),
    ("empty", "COMPLETED"),
])
def test_discovery_metadata_and_v2_report(tmp_path, mode, expected):
    original = report().search_result.archive.source_record
    first = original.rows[0]
    rows = tuple(dict(r, s_region="Circle ICRS 0 0 0.1") for r in original.rows
                 if (r['member_ous_uid'], r['target_name']) ==
                 (first['member_ous_uid'], first['target_name']))
    metadata = replace(original, rows=rows, provenance=replace(
        original.provenance, expected_count=len(rows), retrieved_count=len(rows),
    ))
    row = rows[0]
    candidate = dict(context_id="discovery-identity", project_code=row['proposal_id'],
                     member_ous_uid=row['member_ous_uid'], source_name=row['target_name'])
    _, proposed = mosaic_case()
    mosaic = MosaicAssessmentInput(proposed, tmp_path / 'run', None, 0)
    calls = []

    def discover(*args, **kwargs):
        return dict(status='INCOMPLETE' if mode == 'partial' else 'COMPLETED',
                    plan=dict(recall_status='NOT_ESTABLISHED'),
                    candidates=[] if mode == 'empty' else [candidate])

    def search(spec):
        calls.append(spec)
        assert spec.member_ous_uid == candidate['member_ous_uid']
        assert spec.target_name == candidate['source_name']
        if mode == 'overflow':
            return replace(metadata, status=ArchiveQueryStatus.OVERFLOW)
        if mode == 'wrong_identity':
            return replace(metadata, rows=tuple(dict(r, target_name='wrong') for r in rows))
        return metadata

    result = assess_submitted_line_mosaic_search_v2(
        _wire(geometry='MOSAIC')['request'], mosaic,
        archive_client=SimpleNamespace(search=search), discovery_provider=discover,
    )
    assert result['assessment_status'] == expected
    assert result['schema_version'] == 'submitted_line_mosaic_search_report_1'
    assert result['v2_science']['search_wide_duplication_verdict'] == 'NOT_EVALUATED'
    assert result['assessment'] == 'NOT_AGGREGATED'
    assert json.loads((tmp_path/'run/assessment.json').read_text()) == result
    assert result['discovery']['candidates'] == ([] if mode == 'empty' else [candidate])
    if mode in {'complete', 'partial'}:
        item = result['candidates'][0]
        assert item['member_ous_uid'] == candidate['member_ous_uid']
        assert item['metadata_rows'] == list(rows)
        contexts = item['evaluation']['contexts']
        assert contexts
        for context in contexts:
            assert context['branches'][0]['method_version'] == 'archive_line_context_submitted_or_2'
            for pair in context['line_pairs']:
                assert pair['attempt']['reference']['candidate_context_id'] == context['context_id']
    elif mode == 'empty':
        assert not calls
    else:
        assert result['candidates'][0]['status'] == 'INCOMPLETE'
        assert 'evaluation' not in result['candidates'][0]


def test_invalid_request_never_discovers(tmp_path):
    _, proposed = mosaic_case()
    mosaic = MosaicAssessmentInput(proposed, tmp_path/'run', None, 0)
    with pytest.raises(ValueError, match='MOSAIC geometry'):
        assess_submitted_line_mosaic_search_v2(
            _wire()['request'], mosaic,
            discovery_provider=lambda *a, **k: pytest.fail('Discovery called'),
        )
    assert not mosaic.output_directory.exists()
