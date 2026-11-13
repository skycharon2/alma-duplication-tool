"""Batch preflight must match independently filled standalone forms."""
from copy import deepcopy
from fractions import Fraction

import pytest

from alma_duplicate.proposed_frequency import prepare_frequency
from alma_duplicate.proposed_line import prepare_line_window
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.proposed import validate_form

ROW = 'w123456abcdef'
SOURCES = b'name,ra,dec,redshift\nfirst,02:00:00,-00:30:00,0.685\nsecond,30,-0.5,0\nmissing,0,90,\n'


def form(v2, intents, kind):
    return dict(target_kind='FIXED', geometry='SINGLE_POINTING', setup_id='setup-1',
                sources=['ARCHIVE', 'QUEUE'], intents=intents, angular='0.3',
                radius_mode='AUTO', redshift='9', representative='230.538',
                representative_kind=kind, aggregate='0.3', continuum_setup_declaration='on',
                normal_form_version='2' if v2 else '1', frequency_local_redshift='1',
                continuum_redshift='8', **{
                    ROW+'_id': 'line-1', ROW+'_center': '230.538', ROW+'_center_kind': kind,
                    ROW+'_mode': 'FDM', ROW+'_resolution': '20', ROW+'_rms': '0.3',
                    ROW+'_redshift': '7'})


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    import requests
    from alma_duplicate.ui.runs import BrowserAssessment
    def forbidden(*args, **kwargs):
        pytest.fail('preflight accessed an assessment or external source')
    monkeypatch.setattr(requests.sessions.Session, 'request', forbidden)
    monkeypatch.setattr(BrowserAssessment, 'assess', forbidden)
    monkeypatch.setattr(BrowserAssessment, 'pin_queue_for_submission', forbidden)


@pytest.mark.parametrize('v2', [False, True])
@pytest.mark.parametrize('intents', [['LINE'], ['CONTINUUM'], ['LINE', 'CONTINUUM']])
@pytest.mark.parametrize('kind', ['REST', 'SKY'])
@pytest.mark.parametrize('run', [False, True])
def test_batch_matches_standalone(v2, intents, kind, run):
    values = form(v2, intents, kind)
    before = deepcopy(values)
    rows = [ROW]
    batch = prepare_batch_form(values, rows, SOURCES, require_line_complete=run)
    assert values == before and rows == [ROW]
    for child in batch['sources']:
        source = child['source']
        # Independently fill the ordinary form, including its local-z controls.
        standalone = deepcopy(values)
        standalone.update(target_name=source['name'], ra=source['original']['ra'],
                          dec=source['original']['dec'],
                          ra_format='HMS' if ':' in source['original']['ra'] else 'DEG',
                          dec_format='DMS' if ':' in source['original']['dec'] else 'DEG',
                          redshift=source['redshift'] or '', frequency_local_redshift='0',
                          continuum_redshift='', **{ROW+'_redshift': ''})
        document, validation, _ = validate_form(standalone, rows, require_line_complete=run)
        assert child['document'] == document
        assert child['validation'] == validation
        assert child['document']['request']['representative_frequency']['kind'] == kind
    assert batch['is_valid'] == all(c['validation'].is_valid for c in batch['sources'])
    assert batch['can_search'] == all(c['validation'].can_search for c in batch['sources'])


@pytest.mark.parametrize('v2', [False, True])
@pytest.mark.parametrize('kind', ['REST', 'SKY'])
def test_effective_frequencies_and_missing_redshift(v2, kind):
    batch = prepare_batch_form(form(v2, ['LINE', 'CONTINUUM'], kind), [ROW], SOURCES,
                               require_line_complete=True)
    for child, z in zip(batch['sources'][:2], ['0.685', '0']):
        result = child['validation']
        assert result.is_valid and result.can_search, result.issues
        proposed = result.request
        expected = Fraction('230.538') / (1 + Fraction(z)) if kind == 'REST' else Fraction('230.538')
        line = prepare_line_window(proposed.spectral_windows[0], proposed.sensitivities,
                                   proposed.source_redshift)
        assert Fraction(line.sky_frequency_ghz_exact) == expected
        # V2 owns a separate continuum request; inspect its existing preparation.
        if v2:
            from alma_duplicate.rules.submitted_line_evaluation import prepare_submitted_line_request
            proposed = prepare_submitted_line_request(child['document']['request']).continuum_request
        assert prepare_frequency(proposed.representative_frequency, proposed.source_redshift).sky_ghz_exact == expected
    missing = batch['sources'][2]
    assert 'source_redshift' not in missing['document']['request']
    assert missing['validation'].can_search is (kind == 'SKY')


def test_shared_science_errors_retained_for_every_source():
    values = form(False, ['LINE'], 'SKY') | dict(angular='-1')
    batch = prepare_batch_form(values, [ROW], SOURCES, require_line_complete=True)
    assert len(batch['sources']) == 3 and not batch['is_valid'] and not batch['can_search']
    assert all(c['validation'].errors for c in batch['sources'])


def test_v2_multiple_line_browser_gate_preserved():
    values = form(True, ['LINE'], 'SKY')
    other = 'wabcdef123456'
    for key, value in list(values.items()):
        if key.startswith(ROW):
            values[key.replace(ROW, other)] = 'line-2' if key.endswith('_id') else value
    batch = prepare_batch_form(values, [ROW, other], SOURCES, require_line_complete=True)
    assert not batch['can_search']
    assert all(any(i.code == 'V2_BROWSER_MULTIPLE_LINE_REQUIREMENTS' for i in c['validation'].issues)
               for c in batch['sources'])
