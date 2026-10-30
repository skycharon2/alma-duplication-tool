"""Flask application factory for the thin browser interface."""

import os
import re
from contextlib import nullcontext
from dataclasses import replace
import weakref

from flask import Flask, Response, abort, redirect, render_template, request, session, url_for
from secrets import token_hex

from alma_duplicate.progress import observe_progress
from alma_duplicate.ui.progress import ProgressStore
from alma_duplicate.ui.reports import load_reports
from alma_duplicate.ui.calculation_view import calculation_view, line_preparation
from alma_duplicate.auto_retrieval import automatic_scope
from alma_duplicate.ui.report_view import (
    criterion_view, context_identity, display_number, STATUS_LABELS,
    criterion_explanation, criterion_status, pair_title, standalone_criteria, PURPOSE_LABELS,
    summary_line_conditions,
)
from alma_duplicate.ui.runs import ARCHIVE_CONNECTIONS, BrowserAssessment, RunStore
from alma_duplicate.ui.report_pages import report_page, report_projection
from alma_duplicate.ui.visualization import visualization_data
from alma_duplicate.ui.run_store import DEFAULT_DISK_BYTES, DEFAULT_MAX_AGE
from alma_duplicate.ui.proposed import assessment_supported, contributing_windows, initial_form, read_form, validate_form
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.managed_queue import managed_queue_status
from alma_duplicate.ui.archive_status import archive_configuration_status, archive_run_status
from alma_duplicate.ui.mosaic_form import (
    prepare_mosaic_validation, remove_mosaic_upload, replace_mosaic_upload, restore_mosaic_upload,
)
from alma_duplicate.ui.proposal_form_actions import ProposalFormState, apply_common_edit
from alma_duplicate.ui.workflow_policy import (
    apply_browser_source_policy, initial_mosaic_values, is_fixed_mosaic,
)


def _env_flag(name):
    value = os.environ.get(name)
    if value is None:
        return False

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off", ""}:
        return False

    raise ValueError(f"{name} must be a boolean flag")


def create_app(config=None):
    """Create the browser application without accessing assessment sources."""
    app = Flask(__name__)
    from alma_duplicate.ui.mosaic_uploads import MosaicUploadStore
    mosaic_uploads = MosaicUploadStore()
    app.extensions["mosaic_uploads"] = mosaic_uploads
    app.config.update(SECRET_KEY=token_hex(32), SESSION_COOKIE_NAME='alma_report_history',
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["REPORT_DIRECTORY"] = os.environ.get("ALMA_UI_REPORT_DIR")
    app.config["OFFLINE_ARCHIVE_REPLAY"] = os.environ.get("ALMA_UI_ARCHIVE_REPLAY")
    app.config["LIVE_ARCHIVE"] = _env_flag("ALMA_UI_LIVE_ARCHIVE")
    app.config["LIVE_AQ"] = _env_flag("ALMA_UI_LIVE_ARCHIVE_AQ")
    app.config["SUBMITTED_LINE_V2_UI_ENABLED"] = _env_flag("ALMA_UI_SUBMITTED_LINE_V2")
    app.config["OFFLINE_QUEUE_CSV"] = os.environ.get("ALMA_UI_QUEUE_CSV")
    app.config["MANAGED_QUEUE_ROOT"] = os.environ.get("ALMA_UI_QUEUE_SNAPSHOT_ROOT")
    app.config["ARCHIVE_ARRAY_EVIDENCE"] = os.environ.get("ALMA_UI_ARCHIVE_ARRAY_EVIDENCE")
    app.config["MAX_RETAINED_RUNS"] = 20
    app.config["MAX_RETAINED_BYTES"] = DEFAULT_DISK_BYTES
    app.config["MAX_RUN_AGE_SECONDS"] = DEFAULT_MAX_AGE
    app.config["RUN_STORAGE_PARENT"] = None
    if config is not None:
        app.config.from_mapping(config)

    reports = load_reports(app.config["REPORT_DIRECTORY"])
    configured = BrowserAssessment(
        archive_replay=app.config["OFFLINE_ARCHIVE_REPLAY"],
        queue_csv=app.config["OFFLINE_QUEUE_CSV"],
        managed_queue_root=app.config["MANAGED_QUEUE_ROOT"],
        archive_array_evidence=app.config["ARCHIVE_ARRAY_EVIDENCE"],
        live_archive=app.config["LIVE_ARCHIVE"],
        live_aq=app.config["LIVE_AQ"],
    )
    runs = RunStore(
        app.config["MAX_RETAINED_RUNS"],
        app.config["MAX_RETAINED_BYTES"],
        max_age=app.config["MAX_RUN_AGE_SECONDS"],
        directory=app.config["RUN_STORAGE_PARENT"],
    )
    app.extensions["assessment_runs"] = runs
    weakref.finalize(app, runs.close)
    progress = ProgressStore()
    app.extensions["assessment_progress"] = progress

    @app.before_request
    def expire_runs():
        runs.prune()

    @app.after_request
    def private_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/reports")
    def report_index():
        return render_template("reports.html", reports=reports,
                               recent_runs=runs.summaries(session.get('report_history', [])),
                               retention_hours=runs.max_age / 3600)

    def artifact(report_id):
        if report_id not in reports:
            abort(404)
        return reports[report_id]

    def page_selection(allow_mosaic_views=False):
        page = request.args.get("page", "1")
        if not page.isdecimal() or len(page) > 8 or int(page) < 1:
            abort(400)
        view = request.args.get("view", "matches")
        allowed = (("matches", "all", "matching", "review", "not_met")
                   if allow_mosaic_views else ("matches", "all"))
        if view not in allowed:
            abort(400)
        return int(page), view

    def render_report(data, report_id):
        is_run = data.get('run') is not None
        if data.get("mosaic"):
            return render_template("mosaic_report.html", **data, report_id=report_id,
                                   criterion_view=criterion_view,
                                   criterion_status=criterion_status,
                                   criterion_explanation=criterion_explanation,
                                   pair_title=pair_title, display_number=display_number,
                                   status_labels=STATUS_LABELS)
        return render_template("report.html", **data, report_id=report_id,
                               archive_status=archive_run_status(data['document']),
                               show_technical=request.args.get('technical') == '1',
                               visualization_url=url_for("run_visualization" if is_run else "report_visualization",
                                                         report_id=report_id, page=data["page"] if data["result_view"] == "matches" else 1),
                               criterion_view=criterion_view, criterion_explanation=criterion_explanation,
                               criterion_status=criterion_status, pair_title=pair_title, standalone_criteria=standalone_criteria,
                               summary_line_conditions=summary_line_conditions,
                               purpose_labels=PURPOSE_LABELS, context_identity=context_identity,
                               display_number=display_number, status_labels=STATUS_LABELS,
                               calculation_view=calculation_view, line_preparation=line_preparation,
                               view_endpoint="run_view" if is_run else "report_view",
                               download_endpoint="run_download" if is_run else "report_download")

    @app.get("/reports/<report_id>")
    def report_view(report_id):
        item = artifact(report_id)
        page, view = page_selection()
        try:
            data = report_page(report_projection(item.document, item.inspection), page, view,
                               lambda i: item.document['context_evaluations'][i])
        except IndexError:
            abort(404)
        data.update(item=item, run=None, disk_backed=False)
        return render_report(data, report_id)

    def unavailable_run(report_id):
        reason = runs.unavailable_reason(report_id)
        notices = {
            'EXPIRED': ('Report expired', 'The retention period for this report has ended.'),
            'EVICTED': ('Report removed to free storage',
                        'The server reached its report count or storage retention limit. This earlier report was removed to make room for a newer run.'),
            'OTHER_SESSION': ('Report belongs to another server session',
                              'This link identifies a different server session. Restarting the application ends access to its temporary reports.'),
            'CLOSED': ('Report session ended', 'The server session that stored this report has ended.'),
        }
        title, explanation = notices.get(reason, (
            'Report unavailable',
            'This server has no retained record for this link. Check the URL. Older reports may have expired, been removed, or belonged to a previous server session.',
        ))
        return render_template('run_unavailable.html', title=title, explanation=explanation), 404

    @app.get("/runs/<report_id>")
    def run_view(report_id):
        page, view = page_selection(allow_mosaic_views=True)
        try:
            data = runs.page(report_id, page, view)
        except IndexError:
            abort(404)
        if data is None:
            return unavailable_run(report_id)
        return render_report(data, report_id)

    def render_visualization(data, report_id, is_run):
        plot_page = request.args.get("plot_page", "1")
        if not plot_page.isdecimal() or len(plot_page) > 8 or int(plot_page) < 1:
            abort(400)
        try:
            visual = visualization_data(data, int(plot_page))
        except IndexError:
            abort(404)
        endpoint = "run_visualization" if is_run else "report_visualization"
        return render_template(
            "visualization.html", **data, visual=visual, report_id=report_id,
            visual_endpoint=endpoint,
            visualization_url=url_for(endpoint, report_id=report_id, page=data["page"]),
            report_url=url_for("run_view" if is_run else "report_view", report_id=report_id, page=data["page"]),
        )

    @app.get("/reports/<report_id>/visualization")
    def report_visualization(report_id):
        item = artifact(report_id)
        page, _ = page_selection()
        try:
            data = report_page(report_projection(item.document, item.inspection), page, "matches",
                               lambda i: item.document['context_evaluations'][i])
        except IndexError:
            abort(404)
        return render_visualization(data, report_id, False)

    @app.get("/runs/<report_id>/visualization")
    def run_visualization(report_id):
        page, _ = page_selection()
        try:
            data = runs.page(report_id, page, "matches")
        except IndexError:
            abort(404)
        if data is None:
            return unavailable_run(report_id)
        if data.get("mosaic"):
            abort(404)
        return render_visualization(data, report_id, True)

    @app.get("/runs/<report_id>/download/<kind>")
    def run_download(report_id, kind):
        if kind not in {"report", "inspection", "request"}:
            abort(404)
        download = runs.open_download(report_id, kind)
        if download is None:
            return unavailable_run(report_id)
        response = Response(download, mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="{kind}-{report_id}.json"',
            "Content-Length": str(download.size),
        })
        response.call_on_close(download.close)
        return response

    @app.get("/reports/<report_id>/download/<kind>")
    def report_download(report_id, kind):
        item = artifact(report_id)
        if kind not in {"report", "inspection"}:
            abort(404)
        data = item.raw if kind == "report" else item.inspection_bytes
        return Response(data, mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="{kind}-{report_id}.json"',
        })

    @app.get("/assessment-progress/<token>")
    def assessment_progress(token):
        if re.fullmatch(r"[a-f0-9]{32}", token) is None:
            abort(404)
        state = progress.get(token)
        if state is None:
            abort(404)
        return state

    # The public controllers own their workflow, including legacy Mosaic POSTs.
    # Scientific validation, common form edits, storage and progress stay shared.
    @app.route("/proposed", methods=["GET", "POST"])
    def proposed():
        if request.method == "POST" and is_fixed_mosaic(request.form):
            return _mosaic_controller(legacy_post=True)
        return _single_controller()

    @app.route("/proposed/mosaic", methods=["GET", "POST"])
    def proposed_mosaic():
        return _mosaic_controller()

    def _form_state(*, mosaic=False):
        values, rows = initial_form()
        if mosaic:
            values = initial_mosaic_values(values)
        state = ProposalFormState(values=values, rows=rows)
        state.owner = session.setdefault("mosaic_owner", token_hex(24))
        return state

    def _read_post(state, *, require_mosaic=False):
        try:
            state.values, state.rows = read_form(request.form)
            if state.values.get("archive_connection", "AUTO") not in ARCHIVE_CONNECTIONS:
                raise ValueError("Invalid Archive connection selection")
        except ValueError as exc:
            abort(400, description=str(exc))
        if require_mosaic and not is_fixed_mosaic(state.values):
            abort(400, description="Mosaic form requires a fixed-target Mosaic request")
        state.upload_token, state.mosaic_preview, state.mosaic_preview_error = restore_mosaic_upload(
            state.values, mosaic_uploads, state.owner)
        apply_browser_source_policy(state.values)
        return state.values.get("action", "validate")

    def _download_request(state, action):
        if action == "download" and state.result.is_valid:
            return Response(report_json_text(state.document), mimetype="application/json",
                            headers={"Content-Disposition": 'attachment; filename="proposed-request.json"'})
        return None

    def _run_and_store(state, dispatch):
        """Shared progress and report transport; dispatch owns scientific execution."""
        token = request.headers.get("X-Assessment-Progress")
        if token and re.fullmatch(r"[a-f0-9]{32}", token) is None:
            abort(400)
        if token and not progress.begin(token):
            return Response("Assessment already submitted or server busy. Wait before trying again.", status=429), None
        report_url = None
        try:
            observer = (observe_progress(lambda event: progress.update(token, event))
                        if token else nullcontext())
            with observer:
                runner = replace(configured, archive_connection=state.values.get("archive_connection", "AUTO"))
                document, assessment, extra_input = dispatch(runner)
                if assessment.document is not None:
                    run_id = runs.add(document | extra_input, assessment)
                    history = session.get('report_history', [])
                    session['report_history'] = ([run_id] + history)[:20]
                    report_url = url_for("run_view", report_id=run_id)
                    return ({"report_url": report_url} if token else redirect(report_url, code=303)), None
                return None, "Assessment returned no report. Review input readiness."
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            app.logger.warning("Browser assessment failed: %s", exc)
            return None, "Assessment could not be completed. Check the configured sources and server log. No report was created."
        finally:
            if token:
                progress.finish(token, report_url=report_url)

    def _single_submission(state, action):
        state.document, state.result, state.issues = validate_form(
            state.values, state.rows, require_line_complete=action == "assess")
        if action == "assess":
            if state.values.get("target_kind") == "SUN":
                state.execution_error = "Solar observations are exempt from duplication checking under Appendix A. No assessment or source search was run."
            elif not assessment_supported(state.values):
                state.execution_error = "This observation type cannot be assessed in this browser version. Your inputs are retained. You can validate and export a valid request."
            elif not configured.enabled:
                state.execution_error = "Assessment sources are not configured. You can still validate and download the request."
            elif state.result.is_valid and state.result.can_search:
                response, state.execution_error = _run_and_store(
                    state, lambda runner: (state.document, runner.assess(state.document), {}))
                if response is not None:
                    return response
            else:
                state.execution_error = "Assessment was not run. Correct invalid inputs and supply the search information shown below."
        return _download_request(state, action)

    def _mosaic_submission(state, action):
        state.document, state.result, state.issues = validate_form(
            state.values, state.rows, require_line_complete=action == "assess")
        state.issues, points, state.mosaic_ready, state.execution_error = prepare_mosaic_validation(
            state.values, state.mosaic_preview, state.issues, state.result,
            live_archive=configured.live_archive)
        if action == "assess":
            if not assessment_supported(state.values):
                state.execution_error = "This observation type cannot be assessed in this browser version. Your inputs are retained. You can validate and export a valid request."
            elif not configured.live_archive:
                state.execution_error = "Browser Mosaic assessment requires live Archive configuration. Replay and Queue sources cannot run this workflow."
            elif not configured.enabled:
                state.execution_error = "Assessment sources are not configured. You can still validate and download the request."
            elif state.result.is_valid and (state.result.can_search or points is not None):
                def dispatch_mosaic(runner):
                    from alma_duplicate.ui.mosaic_line_input import is_mosaic_line, submitted_document
                    document = state.document
                    if is_mosaic_line(document) and "line_input_contract" not in document["request"]:
                        document = submitted_document(document)
                    return document, runner.assess_mosaic(document, points), {"mosaic_pointings": points}

                response, state.execution_error = _run_and_store(state, dispatch_mosaic)
                if response is not None:
                    return response
            else:
                state.execution_error = state.execution_error or "Assessment was not run. Correct invalid inputs and supply the search information shown below."
        return _download_request(state, action)

    def _single_controller():
        state = _form_state()
        if request.method == "POST":
            action = _read_post(state)
            if action in {"validate", "download", "assess"}:
                response = _single_submission(state, action)
                if response is not None:
                    return response
            elif action == "preview-pointings":
                abort(400, description="OT preview requires a fixed Mosaic request")
            elif action == "remove-pointings":
                # Preserve old /proposed POST behavior for a stale upload token.
                remove_mosaic_upload(state.values, mosaic_uploads, state.owner, state.upload_token)
                state.mosaic_preview = None
                state.mosaic_preview_error = None
                state.edit_notice = "OT pointings removed."
            elif not apply_common_edit(state, action):
                abort(400)
        return _render_form(state, mosaic_entry=False)

    def _mosaic_controller(*, legacy_post=False):
        state = _form_state(mosaic=True)
        if request.method == "POST":
            action = _read_post(state, require_mosaic=not legacy_post)
            if action == "preview-pointings":
                try:
                    state.mosaic_preview = replace_mosaic_upload(
                        state.values, mosaic_uploads, state.owner, state.upload_token,
                        request.files.getlist("ot_pointings"))
                    state.mosaic_preview_error = None
                except (ValueError, UnicodeError) as exc:
                    state.mosaic_preview_error = str(exc)
            elif action == "remove-pointings":
                remove_mosaic_upload(state.values, mosaic_uploads, state.owner, state.upload_token)
                state.mosaic_preview = None
                state.mosaic_preview_error = None
                state.edit_notice = "OT pointings removed."
            elif action in {"validate", "download", "assess"}:
                response = _mosaic_submission(state, action)
                if response is not None:
                    return response
            elif not apply_common_edit(state, action):
                abort(400)
        # A legacy Mosaic POST must keep the /proposed action and template.
        return _render_form(state, mosaic_entry=not legacy_post)

    def _render_form(state, *, mosaic_entry):
        values, rows = state.values, state.rows
        if state.mosaic_preview:
            state.mosaic_preview["array"] = values.get("mosaic_array", "12m")
            state.mosaic_preview["fixed_icrs_confirmed"] = values.get("mosaic_fixed_icrs") == "on"
            state.mosaic_preview["complete_confirmed"] = values.get("mosaic_complete") == "on"
        for row in rows + values.get("spw_rows", []):
            values.setdefault(row + "_id", row)
        selected = contributing_windows(values)
        from alma_duplicate.ui.normal_line_input import uses_separated_input
        physical_rows = values.get('spw_rows', []) if uses_separated_input(values) else rows
        known_ids = {values[row + "_id"] for row in physical_rows}
        stale_ids = list(dict.fromkeys(value for value in selected if value not in known_ids))
        return render_template("proposed_mosaic.html" if mosaic_entry else "proposed_single.html",
                               values=values, rows=rows,
                               mosaic_entry=mosaic_entry,
                               result=state.result, issues=state.issues, document=state.document,
                               selected_windows=selected, stale_ids=stale_ids,
                               pending_removal=state.pending_removal, edit_notice=state.edit_notice,
                               added_row=state.added_row,
                               purpose_updated=state.purpose_updated,
                               scope_updated=state.scope_updated, assessment_supported=assessment_supported(values),
                               mosaic_preview=state.mosaic_preview, mosaic_preview_error=state.mosaic_preview_error,
                               mosaic_ready=state.mosaic_ready,
                               configured=configured, execution_error=state.execution_error, auto_scope=automatic_scope(),
                               archive_status=archive_configuration_status(configured.archive_kind),
                               queue_status=(managed_queue_status(configured.managed_queue_root)
                                             if configured.managed_queue_root else None))

    @app.post("/sky-preview")
    def sky_preview():
        values = {key: request.form.get(key, "") for key in
                  ("ra", "dec", "ra_format", "dec_format", "target_kind")}
        if values["target_kind"] != "FIXED":
            return {"errors": [{"field": "target_kind", "message": "Sky preview is available for fixed targets only."}]}, 422
        from alma_duplicate.request_validation import validate_preview_position
        position, issues = validate_preview_position({key: values[key] for key in
            ("ra", "dec", "ra_format", "dec_format")} | {"frame": "ICRS"})
        errors = [{"field": issue.path.rsplit(".", 1)[-1], "message": issue.message}
                  for issue in issues]
        if errors or position is None:
            return {"errors": errors or [{"field": "ra", "message": "Enter valid RA and Dec coordinates."}]}, 422
        return {"html": render_template("sky_preview.html", ra=position.ra_deg, dec=position.dec_deg)}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return redirect(url_for("proposed"))

    from alma_duplicate.ui.separated_editor import separated_editor
    app.register_blueprint(separated_editor)

    return app
