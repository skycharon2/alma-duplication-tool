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
from alma_duplicate.ui.proposed import MAX_WINDOWS, assessment_supported, contributing_windows, initial_form, new_row, read_form, validate_form
from alma_duplicate.reporting import report_json_text
from alma_duplicate.ui.managed_queue import managed_queue_status
from alma_duplicate.ui.archive_status import archive_configuration_status, archive_run_status
from alma_duplicate.ui.mosaic_form import (
    prepare_mosaic_validation, remove_mosaic_upload, replace_mosaic_upload, restore_mosaic_upload,
)
from alma_duplicate.ui.workflow_policy import (
    apply_browser_source_policy, initial_mosaic_values, is_fixed_mosaic,
    should_enable_mosaic_v2_on_scope_change,
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

    # Separate public controllers; keep old Mosaic POSTs on /proposed during migration.
    @app.route("/proposed", methods=["GET", "POST"])
    def proposed():
        return _proposed_form(mosaic_entry=False)

    @app.route("/proposed/mosaic", methods=["GET", "POST"])
    def proposed_mosaic():
        return _proposed_form(mosaic_entry=True)

    def _proposed_form(*, mosaic_entry):
        values, rows = initial_form()
        if mosaic_entry:
            values = initial_mosaic_values(values)
        result, issues, document = None, [], None
        pending_removal = None
        edit_notice = None
        added_row = None
        purpose_updated = False
        scope_updated = False
        execution_error = None
        mosaic_preview, mosaic_preview_error = None, None
        mosaic_ready = False
        owner = session.setdefault("mosaic_owner", token_hex(24))
        if request.method == "POST":
            try:
                values, rows = read_form(request.form)
                if values.get("archive_connection", "AUTO") not in ARCHIVE_CONNECTIONS:
                    raise ValueError("Invalid Archive connection selection")
            except ValueError as exc:
                abort(400, description=str(exc))
            # Keep the dedicated Mosaic endpoint in its own fixed-target scope.
            # Existing /proposed submissions retain their compatibility path.
            if mosaic_entry and not is_fixed_mosaic(values):
                abort(400, description="Mosaic form requires a fixed-target Mosaic request")
            token, mosaic_preview, mosaic_preview_error = restore_mosaic_upload(
                values, mosaic_uploads, owner)
            apply_browser_source_policy(values)
            action = values.get("action", "validate")
            if action == "preview-pointings":
                if not is_fixed_mosaic(values):
                    abort(400, description="OT preview requires a fixed Mosaic request")
                try:
                    mosaic_preview = replace_mosaic_upload(
                        values, mosaic_uploads, owner, token,
                        request.files.getlist("ot_pointings"))
                    mosaic_preview_error = None
                except (ValueError, UnicodeError) as exc:
                    mosaic_preview_error = str(exc)
            elif action == "remove-pointings":
                remove_mosaic_upload(values, mosaic_uploads, owner, token)
                mosaic_preview = None
                mosaic_preview_error = None
                edit_notice = "OT pointings removed."
            elif action == "scope":
                # Upgrade a blank Mosaic form only; never reinterpret entered
                # Single Pointing legacy science values as separated V2 records.
                if should_enable_mosaic_v2_on_scope_change(values, rows):
                    values["normal_form_version"] = "2"
                scope_updated = True
                edit_notice = "Observation type updated. Entered values are retained; validate again."
            elif action == "purpose":
                purpose_updated = True
                if "LINE" in values.get("intents", []) and not rows:
                    added_row = new_row()
                    rows.append(added_row)
                edit_notice = "Requirement sections updated. Entered values are retained; validate again."
            elif action == "add-spw":
                spws = values.setdefault("spw_rows", [])
                if len(spws) >= MAX_WINDOWS:
                    abort(400, description="Maximum 32 physical SPW records")
                spws.append(new_row())
                edit_notice = "Physical SPW evidence added. LINE requirements are unchanged."
            elif action.startswith("remove-spw:"):
                row = action.split(":", 1)[1]
                if row not in values.get("spw_rows", []):
                    abort(400)
                values["spw_rows"].remove(row)
                edit_notice = "Physical SPW evidence removed. LINE requirements are unchanged."
            elif action == "add":
                if len(rows) >= MAX_WINDOWS:
                    abort(400, description="Maximum 32 windows in this form")
                added_row = new_row()
                rows.append(added_row)
                edit_notice = "Window added. Validate input to update the diagnostics."
            elif action.startswith(("remove:", "confirm-remove:")):
                row = action.split(":", 1)[1]
                if row not in rows:
                    abort(400)
                if action.startswith("confirm-remove:"):
                    rows.remove(row)
                    edit_notice = "Window removed with its LINE inputs. Review any retained continuum references and validate again."
                else:
                    pending_removal = row
            elif action == "cancel-remove":
                edit_notice = "Window retained. Validate input to update the diagnostics."
            elif action in {"validate", "download", "assess"}:
                document, result, issues = validate_form(values, rows, require_line_complete=action == "assess")
                proposed_points = None
                is_mosaic = is_fixed_mosaic(values)
                if is_mosaic:
                    issues, proposed_points, mosaic_ready, execution_error = prepare_mosaic_validation(
                        values, mosaic_preview, issues, result, live_archive=configured.live_archive)
                if action == "assess":
                    if values.get("target_kind") == "SUN":
                        execution_error = "Solar observations are exempt from duplication checking under Appendix A. No assessment or source search was run."
                    elif not assessment_supported(values):
                        execution_error = "This observation type cannot be assessed in this browser version. Your inputs are retained. You can validate and export a valid request."
                    elif is_mosaic and not configured.live_archive:
                        execution_error = "Browser Mosaic assessment requires live Archive configuration. Replay and Queue sources cannot run this workflow."
                    elif not configured.enabled:
                        execution_error = "Assessment sources are not configured. You can still validate and download the request."
                    elif result.is_valid and (result.can_search or (is_mosaic and proposed_points is not None)):
                        token = request.headers.get("X-Assessment-Progress")
                        if token and re.fullmatch(r"[a-f0-9]{32}", token) is None:
                            abort(400)
                        if token and not progress.begin(token):
                            return Response("Assessment already submitted or server busy. Wait before trying again.", status=429)
                        report_url = None
                        try:
                            observer = (observe_progress(lambda event: progress.update(token, event))
                                        if token else nullcontext())
                            with observer:
                                runner = replace(configured, archive_connection=values.get("archive_connection", "AUTO"))
                                from alma_duplicate.ui.mosaic_line_input import is_mosaic_line, submitted_document
                                if is_mosaic_line(document) and "line_input_contract" not in document["request"]:
                                    document = submitted_document(document)
                                assessment = (runner.assess_mosaic(document, proposed_points) if is_mosaic
                                              else runner.assess(document))
                                if assessment.document is not None:
                                    retained_input = document | ({"mosaic_pointings": proposed_points} if is_mosaic else {})
                                    run_id = runs.add(retained_input, assessment)
                                    history = session.get('report_history', [])
                                    session['report_history'] = ([run_id] + history)[:20]
                                    report_url = url_for("run_view", report_id=run_id)
                                    return {"report_url": report_url} if token else redirect(report_url, code=303)
                                execution_error = "Assessment returned no report. Review input readiness."
                        except (OSError, UnicodeError, ValueError, TypeError) as exc:
                            app.logger.warning("Browser assessment failed: %s", exc)
                            execution_error = "Assessment could not be completed. Check the configured sources and server log. No report was created."
                        finally:
                            if token:
                                progress.finish(token, report_url=report_url)
                    else:
                        execution_error = execution_error or "Assessment was not run. Correct invalid inputs and supply the search information shown below."
                if action == "download" and result.is_valid:
                    return Response(report_json_text(document), mimetype="application/json",
                                    headers={"Content-Disposition": 'attachment; filename="proposed-request.json"'})
            else:
                abort(400)
        if mosaic_preview:
            mosaic_preview["array"] = values.get("mosaic_array", "12m")
            mosaic_preview["fixed_icrs_confirmed"] = values.get("mosaic_fixed_icrs") == "on"
            mosaic_preview["complete_confirmed"] = values.get("mosaic_complete") == "on"
        for row in rows + values.get("spw_rows", []):
            values.setdefault(row + "_id", row)
        selected = contributing_windows(values)
        from alma_duplicate.ui.normal_line_input import uses_separated_input
        physical_rows = values.get('spw_rows', []) if uses_separated_input(values) else rows
        known_ids = {values[row + "_id"] for row in physical_rows}
        stale_ids = list(dict.fromkeys(value for value in selected if value not in known_ids))
        return render_template("proposed.html", values=values, rows=rows,
                               mosaic_entry=mosaic_entry,
                               result=result, issues=issues, document=document,
                               selected_windows=selected, stale_ids=stale_ids,
                               pending_removal=pending_removal, edit_notice=edit_notice, added_row=added_row,
                               purpose_updated=purpose_updated,
                               scope_updated=scope_updated, assessment_supported=assessment_supported(values),
                               mosaic_preview=mosaic_preview, mosaic_preview_error=mosaic_preview_error,
                               mosaic_ready=mosaic_ready,
                               configured=configured, execution_error=execution_error, auto_scope=automatic_scope(),
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
