"""Input snapshots preserve browser input shape before assessment."""
from copy import deepcopy
import json

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.input_snapshot import capture_input_snapshot, restore_input_snapshot
from alma_duplicate.ui.proposal_form_actions import ProposalFormState
from alma_duplicate.ui.proposed import build_document, read_form

LINE = 'w123456abcdef'
OTHER_LINE = 'wabcdef123456'
SPW = 'w112233445566'
OTHER_SPW = 'w665544332211'
SOURCE_BYTES = (b'name,ra,dec,redshift\r\n'
                b'"First target",02:00:00,-00:30:00,0.685\r\n'
                b'Second,30,-0.5,-0.002\r\n'
                b'Third,0,90,\r\n')


def browser_state(*, version, workflow):
    batch = workflow == 'MULTI_SOURCE_SINGLE'
    v2 = version == '2'
    fields = dict(target_kind='FIXED', geometry='MOSAIC' if workflow == 'MOSAIC' else 'SINGLE_POINTING',
        setup_id=' setup-1 ', normal_form_version=version, intents=['CONTINUUM', 'LINE'],
        sources=['QUEUE', 'ARCHIVE'], archive_connection='AUTO', radius_mode='EXPLICIT',
        radius='015.00', radius_unit='arcsec', result_limit='020', angular='0.300',
        angular_unit='arcsec', representative='230538.00', representative_unit='MHz',
        representative_kind='REST', aggregate='0.300', aggregate_unit='mJy/beam',
        continuum_setup_declaration='on', setup_complete='on',
        aggregate_windows=['spw-b', 'spw-a'] if v2 else ['line-b', 'line-a'],
        rows=[LINE] if v2 else [OTHER_LINE, LINE])
    if not batch:
        fields.update(target_name=' B0218+357 ', ra='02:21:05.47', ra_format='HMS',
                      dec='+35:56:13.7', dec_format='DMS', redshift='0.685')
    else:
        fields['source_format'] = 'csv'
    if workflow == 'MOSAIC':
        fields.update(mosaic_array='7m', mosaic_fixed_icrs='on', mosaic_complete='on')
    for row, name in [(LINE, 'line-a'), (OTHER_LINE, 'line-b')]:
        fields.update({f'{row}_{key}': val for key, val in dict(id=name, center='230538.00',
            center_unit='MHz', center_kind='REST' if row == LINE else 'SKY', mode='FDM',
            resolution='20.00', resolution_unit='kHz', rms='0.300', rms_unit='mJy/beam').items()})
    if v2:
        # Keep only the active LINE row, and retain independent SPW order and links.
        fields = {key: val for key, val in fields.items() if not key.startswith(OTHER_LINE)}
        fields.update(frequency_local_redshift='1', continuum_redshift='0.500',
                      spw_rows=[OTHER_SPW, SPW], **{LINE + '_redshift': '-0.001'})
        for row, name in [(SPW, 'spw-a'), (OTHER_SPW, 'spw-b')]:
            fields.update({f'{row}_{key}': val for key, val in dict(id=name, link='line-a' if row == SPW else '',
                bandwidth='1.875', bandwidth_unit='GHz', bandwidth_kind='USABLE').items()})
    else:
        for row in (LINE, OTHER_LINE):
            fields.update({f'{row}_bandwidth': '1875.00', f'{row}_bandwidth_unit': 'MHz',
                           f'{row}_bandwidth_kind': 'USABLE'})
    values, rows = read_form(MultiDict(fields))
    values.pop('rows')
    return ProposalFormState(values, rows)


@pytest.mark.parametrize('workflow', ['SINGLE', 'MULTI_SOURCE_SINGLE', 'MOSAIC'])
@pytest.mark.parametrize('version', ['1', '2'])
def test_roundtrip_preserves_form_and_request(workflow, version):
    original = browser_state(version=version, workflow=workflow)
    snapshot = capture_input_snapshot(original, workflow=workflow)
    restored = restore_input_snapshot(json.loads(json.dumps(snapshot)))

    assert snapshot['form_contract'] == ('V2' if version == '2' else 'LEGACY')
    assert restored.values == original.values
    assert restored.rows == original.rows
    assert build_document(restored.values, restored.rows) == build_document(original.values, original.rows)

    if workflow == 'MULTI_SOURCE_SINGLE':
        original_batch = prepare_batch_form(original.values, original.rows, SOURCE_BYTES)
        restored_batch = prepare_batch_form(restored.values, restored.rows, SOURCE_BYTES,
                                           format=restored.values['source_format'])
        assert restored_batch == original_batch
        assert all(child['validation'].is_valid and child['validation'].can_search
                   for child in restored_batch['sources'][:2])
        assert [child['source']['redshift'] for child in restored_batch['sources']] == ['0.685', '-0.002', None]
        assert [child['source']['name'] for child in restored_batch['sources']] == ['First target', 'Second', 'Third']


def test_capture_omits_transient_fields_and_detaches_edits():
    state = browser_state(version='2', workflow='SINGLE')
    state.upload_token = 'private-upload'
    state.owner = 'private-owner'
    state.edit_notice = 'transient notice'
    state.values.update(csrf='private-csrf', submission_token='private-submission',
                        action='assess', ot_pointings='private-path', arbitrary='unknown',
                        **{OTHER_LINE + '_rms': 'stale', SPW + '_token': 'private-token'})
    snapshot = capture_input_snapshot(state, workflow='SINGLE')
    before = deepcopy(snapshot)
    restored = restore_input_snapshot(snapshot)
    state.values['intents'].clear()
    restored.values['sources'].clear()
    restored.values['spw_rows'].reverse()
    restored.rows.clear()
    assert snapshot == before
    for transient in ('private-', 'transient notice', 'unknown', 'stale'):
        assert transient not in json.dumps(snapshot, ensure_ascii=False)
    assert not restored.owner and not restored.upload_token


@pytest.mark.parametrize('change', [
    {'schema_version': 'future'}, {'workflow': 'UNKNOWN'}, {'form_contract': 'V2'},
    {'unexpected': True}, {'line_rows': ['invalid']}, {'spw_rows': [LINE]},
    {'form_values': {'geometry': 'MOSAIC'}}, {'form_values': {'intents': 'LINE'}},
    {'form_values': {'sources': [42]}}, {'form_values': {'redshift': 0}},
    {'form_values': {'normal_form_version': '99'}}, {'form_values': {'csrf': 'secret'}},
    {'form_values': {'target_name': 'x' * (1024 * 1024)}},
])
def test_restore_rejects_unsupported_or_invalid_shape(change):
    state = browser_state(version='1', workflow='SINGLE')
    snapshot = capture_input_snapshot(state, workflow='SINGLE')
    with pytest.raises(ValueError):
        restore_input_snapshot(snapshot | change)
