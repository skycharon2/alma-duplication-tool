"""Versioned, JSON-ready snapshots of editable assessment form inputs."""

import json
from collections.abc import Mapping

from alma_duplicate.ui.normal_line_input import uses_separated_input
from alma_duplicate.ui.proposal_form_actions import ProposalFormState
from alma_duplicate.ui.proposed import MAX_WINDOWS, ROW

SCHEMA_VERSION = 'assessment_input_snapshot_1'
MAX_SNAPSHOT_BYTES = 1024 * 1024
_WORKFLOWS = {
    'SINGLE': 'SINGLE_POINTING',
    'MULTI_SOURCE_SINGLE': 'SINGLE_POINTING',
    'MOSAIC': 'MOSAIC',
}
_FIELDS = frozenset('''
    target_kind geometry target_name ra dec ra_format dec_format redshift
    setup_id setup_complete line_evaluation_scope normal_form_version
    normal_line_records frequency_local_redshift continuum_redshift
    angular angular_unit representative representative_unit representative_kind
    aggregate aggregate_unit continuum_setup_declaration
    radius radius_unit radius_mode result_limit archive_connection
    source_format mosaic_array mosaic_fixed_icrs mosaic_complete
'''.split())
_LIST_FIELDS = frozenset({'intents', 'sources', 'aggregate_windows'})
_LINE_SUFFIXES = (
    'id', 'center', 'center_unit', 'center_kind', 'mode', 'bandwidth',
    'bandwidth_unit', 'bandwidth_kind', 'rms', 'rms_unit', 'resolution',
    'resolution_unit', 'redshift',
)
_SPW_SUFFIXES = ('id', 'link', 'bandwidth', 'bandwidth_unit', 'bandwidth_kind')
_SNAPSHOT_KEYS = {'schema_version', 'workflow', 'form_contract', 'form_values', 'line_rows', 'spw_rows'}


def _row_ids(rows):
    if (not isinstance(rows, list) or len(rows) > MAX_WINDOWS
            or any(not isinstance(row, str) or not ROW.fullmatch(row) for row in rows)
            or len(set(rows)) != len(rows)):
        raise ValueError('Invalid assessment snapshot row identifiers')
    return list(rows)


def _rows(line_rows, spw_rows):
    line_rows, spw_rows = _row_ids(line_rows), _row_ids(spw_rows)
    if set(line_rows).intersection(spw_rows):
        raise ValueError('LINE and physical SPW rows must have distinct identifiers')
    return line_rows, spw_rows


def _allowed_fields(line_rows, spw_rows):
    return (_FIELDS | _LIST_FIELDS
            | {f'{row}_{suffix}' for row in line_rows for suffix in _LINE_SUFFIXES}
            | {f'{row}_{suffix}' for row in spw_rows for suffix in _SPW_SUFFIXES})


def _form_values(values, allowed, *, strict):
    if not isinstance(values, Mapping):
        raise ValueError('Assessment snapshot form values must be a mapping')
    if strict and values.keys() - allowed:
        raise ValueError('Unsupported assessment snapshot fields')
    retained = {}
    for key, value in values.items():
        if key not in allowed:
            continue
        if key in _LIST_FIELDS and isinstance(value, list) and all(isinstance(item, str) for item in value):
            retained[key] = list(value)
        elif isinstance(value, str) and (key not in _LIST_FIELDS or key == 'aggregate_windows'):
            retained[key] = value
        else:
            raise ValueError(f'Invalid assessment snapshot form value for {key}')
    return retained


def _contract(workflow, values):
    if not isinstance(workflow, str) or workflow not in _WORKFLOWS:
        raise ValueError('Unsupported assessment snapshot workflow')
    if values.get('geometry', 'SINGLE_POINTING') != _WORKFLOWS[workflow]:
        raise ValueError('Assessment snapshot workflow disagrees with form geometry')
    if values.get('normal_form_version', '') not in {'', '1', '2'}:
        raise ValueError('Unsupported assessment snapshot form version')
    return 'V2' if uses_separated_input(values) else 'LEGACY'


def _check_size(snapshot):
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError('Assessment snapshot exceeds the size limit')


def capture_input_snapshot(state: ProposalFormState, *, workflow: str) -> dict:
    """Copy only allowlisted editable inputs; no validation or assessment is run."""
    line_rows, spw_rows = _rows(state.rows, state.values.get('spw_rows', []))
    values = _form_values(state.values, _allowed_fields(line_rows, spw_rows), strict=False)
    snapshot = dict(schema_version=SCHEMA_VERSION, workflow=workflow,
                    form_contract=_contract(workflow, values), form_values=values,
                    line_rows=line_rows, spw_rows=spw_rows)
    _check_size(snapshot)
    return snapshot


def restore_input_snapshot(snapshot: Mapping) -> ProposalFormState:
    """Validate a decoded snapshot and return an independent editable form."""
    if not isinstance(snapshot, Mapping) or snapshot.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported assessment input snapshot schema')
    if snapshot.keys() != _SNAPSHOT_KEYS:
        raise ValueError('Invalid assessment input snapshot structure')
    line_rows, spw_rows = _rows(snapshot['line_rows'], snapshot['spw_rows'])
    values = _form_values(snapshot['form_values'], _allowed_fields(line_rows, spw_rows), strict=True)
    if snapshot['form_contract'] != _contract(snapshot['workflow'], values):
        raise ValueError('Assessment snapshot form contract disagrees with form values')
    _check_size(dict(snapshot, form_values=values))
    values['spw_rows'] = spw_rows
    return ProposalFormState(values=values, rows=line_rows)
