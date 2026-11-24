"""Create short-lived browser-owned drafts from saved assessment inputs."""

import os
import re
from secrets import compare_digest, token_hex
import weakref

from flask import Blueprint, abort, redirect, request, session, url_for

from alma_duplicate.ui.input_snapshot import restore_input_snapshot
from alma_duplicate.ui.owned_uploads import OwnedUploadStore

_ENDPOINTS = {
    'SINGLE': 'proposed',
    'MULTI_SOURCE_SINGLE': 'batch.proposed',
    'MOSAIC': 'proposed_mosaic',
}
_UPLOAD_HINTS = {
    'MULTI_SOURCE_SINGLE': 'Upload the source list again before validating.',
    'MOSAIC': 'Import the OT pointing file again before validating.',
}
_TOKEN = re.compile(r'[a-f0-9]{48}\Z')
_CSRF = re.compile(r'[a-f0-9]{64}\Z')


def register_assessment_reuse(app, runs):
    ttl = app.config.get('ASSESSMENT_DRAFT_TTL_SECONDS')
    if ttl is None:
        ttl = int(os.environ.get('ALMA_ASSESSMENT_DRAFT_TTL_SECONDS', '1800'))
    if type(ttl) is not int or ttl < 1:
        raise ValueError('Assessment draft lifetime must be a positive number of seconds')
    drafts = OwnedUploadStore(ttl=ttl)
    app.extensions['assessment_drafts'] = drafts
    weakref.finalize(app, drafts.close)
    routes = Blueprint('assessment_reuse', __name__)

    @app.context_processor
    def reuse_token():
        if request.endpoint != 'report_index':
            return {}
        return {'assessment_reuse_csrf': session.setdefault('assessment_reuse_csrf', token_hex(32))}

    def start_draft(parent_id, load_saved):
        tokens = request.form.getlist('csrf')
        expected = session.get('assessment_reuse_csrf')
        if (len(tokens) != 1 or not _CSRF.fullmatch(tokens[0]) or not expected
                or not compare_digest(tokens[0], expected)):
            abort(403, description='The reuse request expired. Open Existing reports again.')
        owner = session.get('batch_owner')
        if not owner:
            abort(404)
        try:
            saved = load_saved(parent_id)
        except (OSError, ValueError, KeyError, TypeError):
            abort(409, description='The saved assessment inputs could not be read.')
        if saved is None:
            abort(404)
        snapshot = saved['snapshot']
        try:
            token = drafts.put(owner, snapshot)
        except ValueError:
            abort(503, description='Draft storage is busy. Try again later.')
        return redirect(url_for(_ENDPOINTS[snapshot['workflow']], draft=token), code=303)

    @routes.post('/runs/<run_id>/reuse')
    def reuse_run(run_id):
        return start_draft(run_id, runs.input_for_report)

    @routes.post('/batches/<batch_id>/reuse')
    def reuse_batch(batch_id):
        return start_draft(batch_id, runs.input_for_batch)

    app.register_blueprint(routes)


def load_draft_form(app, workflow):
    """Restore only on GET. The ordinary form POST handles edits and execution."""
    tokens = request.args.getlist('draft')
    if request.method != 'GET' or not tokens:
        return None
    drafts = app.extensions.get('assessment_drafts')
    if drafts is None or len(tokens) != 1 or not _TOKEN.fullmatch(tokens[0]):
        abort(404)
    snapshot = drafts.get(session.get('batch_owner'), tokens[0])
    if snapshot is None or snapshot['workflow'] != workflow:
        abort(404)
    state = restore_input_snapshot(snapshot)
    notice = 'Settings restored from a previous assessment. Review the inputs before running a new assessment.'
    if workflow in _UPLOAD_HINTS:
        notice += ' ' + _UPLOAD_HINTS[workflow]
    state.edit_notice = notice
    return state
