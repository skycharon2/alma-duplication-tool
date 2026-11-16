"""Owner-scoped upload, preflight, execution and saved batch presentation."""
from copy import deepcopy
from hashlib import sha256
import re
from secrets import compare_digest, token_hex
import weakref

from flask import Blueprint, Response, abort, redirect, render_template, request, session, url_for

from alma_duplicate.parsers.source_list import MAX_BYTES, parse_source_list
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.batch_assessment import BatchValidationError, execute_batch
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.form_context import form_context
from alma_duplicate.ui.owned_uploads import OwnedUploadStore
from alma_duplicate.ui.proposal_form_actions import ProposalFormState, apply_common_edit
from alma_duplicate.ui.proposed import initial_form, read_form
from alma_duplicate.ui.runs import ARCHIVE_CONNECTIONS


def register_batch_routes(app, configured, runs, progress):
    routes = Blueprint('batch', __name__)
    uploads = OwnedUploadStore()
    app.extensions['source_uploads'] = uploads
    weakref.finalize(app, uploads.close)

    def progress_key(owner, token):
        return sha256((owner + ':' + token).encode()).hexdigest()

    @app.context_processor
    def report_batch_navigation():
        # Scope by endpoint, never by arbitrary query-string IDs. Standalone and
        # preloaded reports keep their existing presentation and URL behavior.
        if request.endpoint not in {'run_view', 'run_visualization', 'run_queue_view', 'run_download'}:
            return {}
        run_id = (request.view_args or {}).get('report_id')
        owner = session.get('batch_owner')
        if not run_id or not owner:
            return {}
        link = runs.batches.lookup_run(run_id, owner)
        if link is None:
            return {}
        manifest = runs.batches.get(link['batch_id'], owner)
        if manifest is None:
            return {}
        from alma_duplicate.ui.batch_navigation import navigation_context
        navigation = navigation_context(manifest, link['source_id'], link['purpose'],
                                        visual=request.endpoint == 'run_visualization')
        if navigation is None:
            return {}
        def destination_url(destination):
            if destination['run_id']:
                return url_for(destination['endpoint'], report_id=destination['run_id'])
            return url_for('batch.overview', batch_id=manifest['batch_id'],
                           _anchor='source-' + destination['source_id'])
        for destination in [navigation['previous'], navigation['next'], *navigation['purposes']]:
            if destination is not None:
                destination['url'] = destination_url(destination)
        current_id = navigation['current']['run_id']
        navigation['text_url'] = url_for('run_view', report_id=current_id) if current_id else None
        navigation['visual_url'] = url_for('run_visualization', report_id=current_id) if current_id else None
        return {'batch_navigation': navigation}

    @routes.get('/batches/progress/<token>')
    def progress_view(token):
        owner = session.get('batch_owner')
        if not owner or re.fullmatch('[a-f0-9]{32}', token) is None:
            abort(404)
        state = progress.get(progress_key(owner, token))
        if state is None:
            abort(404)
        return state

    @routes.route('/proposed/batch', methods=['GET', 'POST'])
    def proposed():
        owner = session.setdefault('batch_owner', token_hex(24))
        csrf = session.setdefault('batch_csrf', token_hex(32))
        values, rows = initial_form()
        values.update(target_kind='FIXED', geometry='SINGLE_POINTING')
        state = ProposalFormState(values=values, rows=rows, owner=owner)
        upload = None
        preview = None
        preflights = None
        submission = token_hex(16)
        if request.method == 'POST':
            posted_csrf = request.form.get('batch_csrf', '')
            if re.fullmatch('[a-f0-9]{64}', posted_csrf) is None or not compare_digest(posted_csrf, csrf):
                abort(400, description='Form expired. Reload the batch input page.')
            try:
                state.values, state.rows = read_form(request.form)
                if (state.values.get('target_kind') != 'FIXED' or
                        state.values.get('geometry') != 'SINGLE_POINTING'):
                    raise ValueError('Batch input requires fixed Single Pointing targets')
                if state.values.get('archive_connection', 'AUTO') not in ARCHIVE_CONNECTIONS:
                    raise ValueError('Invalid Archive connection')
                action = state.values.get('action', 'validate')
                submission = state.values.get('submission_token', '')
                if re.fullmatch('[a-f0-9]{32}', submission) is None:
                    raise ValueError('Invalid submission token; reload the form')
            except ValueError as exc:
                abort(400, description=str(exc))
            token = state.values.get('source_upload_token', '')
            upload = uploads.get(owner, token) if token else None
            files = request.files.getlist('source_list')
            supplied = [f for f in files if f.filename]
            if supplied or action == 'preview-sources':
                # A failed replacement must not leave the old list eligible to run.
                uploads.remove(owner, token)
                state.values.pop('source_upload_token', None)
                upload = None
                try:
                    if len(files) != 1 or len(supplied) != 1:
                        raise ValueError('Choose one source-list file.')
                    raw = supplied[0].read(MAX_BYTES + 1)
                    format = state.values.get('source_format', 'csv')
                    preview = parse_source_list(raw, format=format)
                    upload = dict(raw=raw, format=format, preview=preview)
                    state.values['source_upload_token'] = uploads.put(owner, upload)
                    state.edit_notice = 'Source list imported. Review each row before running.'
                except (ValueError, UnicodeError) as exc:
                    state.execution_error = str(exc)
                    upload = None
            if action == 'remove-sources':
                uploads.remove(owner, state.values.pop('source_upload_token', ''))
                upload = None
                preview = None
                state.edit_notice = 'Source list removed.'
            elif action in {'validate', 'assess'}:
                if upload is None:
                    state.execution_error = state.execution_error or 'Upload your source list again; it is missing, expired or belongs to another browser.'
                else:
                    preview = upload['preview']
                    if not preview['is_valid']:
                        state.execution_error = 'Correct all source-list errors and upload the revised file.'
                    else:
                        try:
                            preflights = {'combined': prepare_batch_form(state.values, state.rows,
                                upload['raw'], format=upload['format'], require_line_complete=True)}
                            if action == 'assess':
                                response = assess(state, upload, submission, preflights)
                                if response is not None:
                                    return response
                        except BatchValidationError as exc:
                            preflights = exc.preflights
                            state.execution_error = str(exc)
                        except (ValueError, KeyError, OSError) as exc:
                            app.logger.warning('Batch submission unavailable: %s', exc)
                            state.execution_error = 'Assessment could not start or its batch record became unavailable. Validate the inputs again before retrying.'
            elif action not in {'preview-sources', 'remove-sources'} and not apply_common_edit(state, action):
                abort(400)
            if action != 'assess':
                submission = token_hex(16)
        if upload is not None:
            preview = upload['preview']
        if state.execution_error:
            submission = token_hex(16)
        return render_template('proposed_batch.html', **form_context(state, configured),
            batch_entry=True, mosaic_entry=False, preview=preview, preflights=preflights,
            batch_csrf=csrf, submission_token=submission,
            form_action=url_for('batch.proposed'),
            batch_progress_url=url_for('batch.progress_view', token='TOKEN'))

    def assess(state, upload, submission, preflights):
        combined = preflights['combined']
        if not combined['is_valid'] or not combined['can_search']:
            state.execution_error = 'Correct the input diagnostics for every target before running.'
            return None
        header = request.headers.get('X-Assessment-Progress')
        key = None
        if header is not None:
            if re.fullmatch('[a-f0-9]{32}', header) is None:
                abort(400)
            key = progress_key(state.owner, header)
            if not progress.begin(key):
                return Response('Assessment already submitted or server busy.', status=429)
        report_url = None
        try:
            batch_id = execute_batch(state.values, state.rows, upload['raw'], runner=configured,
                runs=runs, owner=state.owner, submission_token=submission, format=upload['format'],
                max_workers=app.config['BATCH_MAX_WORKERS'],
                progress=(lambda event: progress.update(key, event)) if key else None)
            session['batch_history'] = list(dict.fromkeys([batch_id] + session.get('batch_history', [])))[:20]
            report_url = url_for('batch.overview', batch_id=batch_id)
            return {'report_url': report_url} if header else redirect(report_url, code=303)
        finally:
            if key:
                progress.finish(key, report_url=report_url)

    def owned_manifest(batch_id):
        manifest = runs.batches.get(batch_id, session.get('batch_owner'))
        if manifest is None:
            return None
        return manifest

    @routes.get('/batches/<batch_id>')
    def overview(batch_id):
        manifest = owned_manifest(batch_id)
        if manifest is None:
            return render_template('batch_unavailable.html'), 404
        for source in manifest['sources']:
            for report in source['reports']:
                report['overview'] = None
                if report['availability'] == 'AVAILABLE':
                    try:
                        report['overview'] = runs.overview(report['run_id'])
                    except (OSError, ValueError):
                        report['availability'] = 'UNREADABLE'
                    if report['overview'] is None and report['availability'] == 'AVAILABLE':
                        report['availability'] = runs.unavailable_reason(report['run_id']) or 'UNKNOWN'
        shared = deepcopy(manifest['shared_setup']['document']['request'])
        for name in ('position', 'target_name', 'source_redshift'):
            shared.pop(name, None)
        for line in shared.get('line_requirements', []):
            line.pop('source_redshift', None)
        if isinstance(shared.get('continuum_requirement'), dict):
            shared['continuum_requirement'].pop('source_redshift', None)
        return render_template('batch_overview.html', batch=manifest, shared=shared,
                               unavailable_reports=sum(r['state'] == 'COMPLETED' and r['availability'] != 'AVAILABLE'
                                                       for s in manifest['sources'] for r in s['reports']),
                               retention_hours=runs.max_age / 3600)

    @routes.get('/batches/<batch_id>/download/manifest')
    def download_manifest(batch_id):
        manifest = owned_manifest(batch_id)
        if manifest is None:
            abort(404)
        return Response(report_json_text(manifest), mimetype='application/json',
                        headers={'Content-Disposition': 'attachment; filename="batch-manifest.json"'})

    app.register_blueprint(routes)
