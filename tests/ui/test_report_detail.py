"""Matching detail retention changes representation, never scientific decisions."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from alma_duplicate import assessment, reporting
from alma_duplicate.cli.acceptance import load_catalog
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.ui.runs import BrowserAssessment

ROOT = Path(__file__).parents[2]
CASES = load_catalog(ROOT / 'examples/acceptance/catalog.json')[1]


def assert_preserved(full, compact):
    assert full['report_version'] == '4' and compact['report_version'] == '5'
    for key in ('evaluation_scope', 'request_criteria', 'sources', 'evaluation_configuration'):
        assert full[key] == compact[key]
    assert len(full['context_evaluations']) == len(compact['context_evaluations'])
    for before, after in zip(full['context_evaluations'], compact['context_evaluations'], strict=True):
        for key in ('context_id', 'reference', 'display_identity', 'branches'):
            assert before[key] == after[key]
        matched = any(b['status'] == 'CRITERIA_MET' for b in before['branches'])
        if matched:
            assert after == before | {'detail_level': 'FULL'}
        else:
            assert after['detail_level'] == 'SUMMARY'
            assert 'line_pairing' not in after and 'evidence_states' not in after
            for a, b in zip(before.get('beam_variants') or [before],
                            after.get('beam_variants') or [after], strict=True):
                assert a['branches'] == b['branches']
                assert len(a['line_pairs']) == len(b['line_pairs'])
                for x, y in zip(a['line_pairs'], b['line_pairs'], strict=True):
                    for key in ('status', 'truth', 'method_version', 'reasons'):
                        assert x[key] == y[key]
                    assert x['attempt'].get('reference') == y['attempt'].get('reference')
                    assert 'proposed' not in y['attempt'] and 'candidate' not in y['attempt']
    # Pair identity, missing evidence, source failures and diagnostic counts agree.
    a, b = inspect_report(full), inspect_report(compact)
    b['report_version'] = '4'
    assert a == b


@pytest.mark.parametrize('case,inputs,unused', CASES, ids=[c['case_id'] for c, _, _ in CASES])
def test_full_and_matching_reports_preserve_all_decisions(case, inputs, unused, monkeypatch):
    typed = []
    original = assessment.report_document

    def capture(report, **kwargs):
        typed.append((report, kwargs))
        return original(report, **kwargs)

    monkeypatch.setattr(assessment, 'report_document', capture)
    calls = []
    full_results = reporting._context_results

    def observed(item):
        calls.append(id(item))
        return full_results(item)

    monkeypatch.setattr(reporting, '_context_results', observed)
    request = json.loads(inputs['request'].read_text())
    compact = BrowserAssessment(archive_replay=inputs.get('archive_replay'),
                                queue_csv=inputs.get('queue_csv')).assess(request).document
    # Nonmatching roots never visit the expensive full-evidence conversion.
    for item in typed[0][0].context_evaluations:
        if not any(b.status == 'CRITERIA_MET' for b in item.branches):
            assert id(item) not in calls
    full = reporting.report_document(typed[0][0], **(typed[0][1] | {'detail': 'full'}))
    assert_preserved(full, compact)


@pytest.mark.parametrize('source', ['ARCHIVE', 'QUEUE'])
@pytest.mark.parametrize('offset', [0, 16, 25])
def test_beam_variants_remain_separate_in_full_and_summary_records(source, offset):
    if source == 'ARCHIVE':
        from tests.integration.test_archive_array_adapter import synthetic
        search, catalog = synthetic(offset=offset, intents=('CONTINUUM', 'LINE'))
        report = evaluate_candidate_search(search, archive_arrays=catalog)
    else:
        from tests.integration.test_queue_beam_variants import mixed
        _, report, _ = mixed(offset=offset, intents=('CONTINUUM', 'LINE'))
    full = reporting.report_document(report)
    compact = reporting.report_document(report, detail='matches')
    assert_preserved(full, compact)
    assert [v['diameter_m'] for v in compact['context_evaluations'][0]['beam_variants']] == [7, 12]


def test_invalid_detail_policy_is_rejected_before_source_access():
    with pytest.raises(ValueError, match='Report detail'):
        assessment.assess_observation({}, {}, report_detail='unknown')
    with pytest.raises(ValueError, match='Report detail'):
        BrowserAssessment(report_detail='unknown')


def test_reader_rejects_mislabelled_compact_records():
    request = json.loads((ROOT / 'examples/confirmed_line/request.json').read_text())
    doc = BrowserAssessment(archive_replay=ROOT / 'examples/confirmed_line/archive/manifest.json').assess(request).document
    for mutation in ('policy', 'counts', 'level'):
        bad = deepcopy(doc)
        if mutation == 'policy':
            bad['report_detail']['version'] = 'unknown'
        elif mutation == 'counts':
            bad['report_detail']['summary_contexts'] += 1
        else:
            bad['context_evaluations'][0]['detail_level'] = 'missing'
        with pytest.raises(ValueError):
            inspect_report(bad)
