"""Create short-lived browser-owned drafts from saved assessment inputs."""

from io import BytesIO
import os
import re
from secrets import compare_digest, token_hex
import weakref

from flask import Blueprint, abort, redirect, request, session, url_for
from werkzeug.datastructures import FileStorage

from alma_duplicate.parsers.source_list import parse_source_list
from alma_duplicate.ui.input_snapshot import restore_input_snapshot
from alma_duplicate.ui.mosaic_form import prepare_mosaic_upload
from alma_duplicate.ui.owned_uploads import OwnedUploadStore

_ENDPOINTS = {
    'SINGLE': 'proposed',
    'MULTI_SOURCE_SINGLE': 'batch.proposed',
    'MOSAIC': 'proposed_mosaic',
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
        workflow = snapshot['workflow']
        upload = None
        upload_owner = owner
        if workflow == 'MULTI_SOURCE_SINGLE':
            uploads = app.extensions['source_uploads']
            upload = saved['upload']
            try:
                preview = parse_source_list(upload['raw'], format=upload['format'])
                if not preview['is_valid'] or preview['input_sha256'] != upload['input_sha256']:
                    raise ValueError('Saved source list does not match its preview')
                upload = dict(upload, preview=preview, restored=True)
            except (ValueError, KeyError, TypeError):
                abort(409, description='The saved source list could not be restored.')
        elif workflow == 'MOSAIC':
            uploads = app.extensions['mosaic_uploads']
            upload_owner = session.setdefault('mosaic_owner', token_hex(24))
            try:
                original = saved['upload']
                with BytesIO(original['raw']) as stream:
                    upload = prepare_mosaic_upload(
                        FileStorage(stream=stream, filename=original['filename']),
                        snapshot['form_values'])
                if upload['input_sha256'] != original['input_sha256']:
                    raise ValueError('Saved OT pointings do not match their preview')
                upload['preview']['restored'] = True
            except (ValueError, KeyError, TypeError):
                abort(409, description='The saved OT pointing file could not be restored.')
        upload_token = None
        try:
            if upload is not None:
                upload_token = uploads.put(upload_owner, upload)
            original_url = (
                url_for('batch.overview', batch_id=parent_id) if workflow == 'MULTI_SOURCE_SINGLE'
                else url_for('run_view', report_id=parent_id)
            )
            token = drafts.put(owner, dict(snapshot=snapshot, upload_token=upload_token,
                                           original_url=original_url))
        except ValueError:
            if upload_token is not None:
                uploads.remove(upload_owner, upload_token)
            abort(503, description='Draft storage is busy. Try again later.')
        return redirect(url_for(_ENDPOINTS[workflow], draft=token), code=303)

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
    draft = drafts.get(session.get('batch_owner'), tokens[0])
    if draft is None or draft['snapshot']['workflow'] != workflow:
        abort(404)
    state = restore_input_snapshot(draft['snapshot'])
    state.upload_token = draft['upload_token'] or ''
    state.original_assessment_url = draft['original_url']
    state.edit_notice = ('Settings restored from a previous assessment. '
                         'Review or modify the inputs, then validate and run a new assessment.')
    return state
