"""Flask application factory for the thin browser interface."""

import os
import weakref

from flask import Flask, Response, abort, redirect, render_template, request, url_for

from alma_duplicate.ui.reports import load_reports
from alma_duplicate.auto_retrieval import automatic_scope
from alma_duplicate.ui.report_view import (
    criterion_view, context_identity, display_number, STATUS_LABELS,
    criterion_explanation, criterion_status, pair_title, standalone_criteria, PURPOSE_LABELS,
)
from alma_duplicate.ui.runs import BrowserAssessment, RunStore
from alma_duplicate.ui.report_pages import report_page, report_projection
from alma_duplicate.ui.run_store import DEFAULT_DISK_BYTES, DEFAULT_MAX_AGE
from alma_duplicate.ui.proposed import MAX_WINDOWS, assessment_supported, contributing_windows, initial_form, new_row, read_form, validate_form
from alma_duplicate.reporting import report_json_text


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
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["REPORT_DIRECTORY"] = os.environ.get("ALMA_UI_REPORT_DIR")
    app.config["OFFLINE_ARCHIVE_REPLAY"] = os.environ.get("ALMA_UI_ARCHIVE_REPLAY")
    app.config["LIVE_ARCHIVE"] = _env_flag("ALMA_UI_LIVE_ARCHIVE")
    app.config["LIVE_AQ"] = _env_flag("ALMA_UI_LIVE_ARCHIVE_AQ")
    app.config["OFFLINE_QUEUE_CSV"] = os.environ.get("ALMA_UI_QUEUE_CSV")
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
        return render_template("reports.html", reports=reports)

    def artifact(report_id):
        if report_id not in reports:
            abort(404)
        return reports[report_id]

    def page_selection():
        page = request.args.get("page", "1")
        if not page.isdecimal() or len(page) > 8 or int(page) < 1:
            abort(400)
        view = request.args.get("view", "matches")
        if view not in ("matches", "all"):
            abort(400)
        return int(page), view

    def render_report(data, report_id):
        is_run = data.get('run') is not None
        return render_template("report.html", **data, report_id=report_id,
                               criterion_view=criterion_view, criterion_explanation=criterion_explanation,
                               criterion_status=criterion_status, pair_title=pair_title, standalone_criteria=standalone_criteria,
                               purpose_labels=PURPOSE_LABELS, context_identity=context_identity,
                               display_number=display_number, status_labels=STATUS_LABELS,
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

    def unavailable_run():
        abort(404, description="Run unavailable: unknown ID, application restarted, expired, or retention limit reached.")

    @app.get("/runs/<report_id>")
    def run_view(report_id):
        page, view = page_selection()
        try:
            data = runs.page(report_id, page, view)
        except IndexError:
            abort(404)
        if data is None:
            unavailable_run()
        return render_report(data, report_id)

    @app.get("/runs/<report_id>/download/<kind>")
    def run_download(report_id, kind):
        if kind not in {"report", "inspection", "request"}:
            abort(404)
        download = runs.open_download(report_id, kind)
        if download is None:
            unavailable_run()
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

    @app.route("/proposed", methods=["GET", "POST"])
    def proposed():
        values, rows = initial_form()
        result, issues, document = None, [], None
        pending_removal = None
        edit_notice = None
        added_row = None
        purpose_updated = False
        scope_updated = False
        execution_error = None
        if request.method == "POST":
            try:
                values, rows = read_form(request.form)
            except ValueError as exc:
                abort(400, description=str(exc))
            action = values.get("action", "validate")
            if action == "scope":
                scope_updated = True
                edit_notice = "Observation type updated. Entered values are retained; validate again."
            elif action == "purpose":
                purpose_updated = True
                if "LINE" in values.get("intents", []) and not rows:
                    added_row = new_row()
                    rows.append(added_row)
                edit_notice = "Requirement sections updated. Entered values are retained; validate again."
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
                document, result, issues = validate_form(values, rows)
                if action == "assess":
                    if values.get("target_kind") == "SUN":
                        execution_error = "Solar observations are exempt from duplication checking under Appendix A. No assessment or source search was run."
                    elif not assessment_supported(values):
                        execution_error = "This observation type cannot be assessed in this browser version. Your inputs are retained. You can validate and export a valid request."
                    elif not configured.enabled:
                        execution_error = "Assessment sources are not configured. You can still validate and download the request."
                    elif result.is_valid and result.can_search:
                        try:
                            assessment = configured.assess(document)
                            if assessment.document is not None:
                                run_id = runs.add(document, assessment)
                                return redirect(url_for("run_view", report_id=run_id), code=303)
                            execution_error = "Assessment returned no report. Review input readiness."
                        except (OSError, UnicodeError, ValueError, TypeError) as exc:
                            app.logger.warning("Browser assessment failed: %s", exc)
                            execution_error = "Assessment could not be completed. Check the configured sources and server log. No report was created."
                    else:
                        execution_error = "Assessment was not run. Correct invalid inputs and supply the search information shown below."
                if action == "download" and result.is_valid:
                    return Response(report_json_text(document), mimetype="application/json",
                                    headers={"Content-Disposition": 'attachment; filename="proposed-request.json"'})
            else:
                abort(400)
        for row in rows:
            values.setdefault(row + "_id", row)
        selected = contributing_windows(values)
        known_ids = {values[row + "_id"] for row in rows}
        stale_ids = list(dict.fromkeys(value for value in selected if value not in known_ids))
        return render_template("proposed.html", values=values, rows=rows,
                               result=result, issues=issues, document=document,
                               selected_windows=selected, stale_ids=stale_ids,
                               pending_removal=pending_removal, edit_notice=edit_notice, added_row=added_row,
                               purpose_updated=purpose_updated,
                               scope_updated=scope_updated, assessment_supported=assessment_supported(values),
                               configured=configured, execution_error=execution_error, auto_scope=automatic_scope())

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return redirect(url_for("proposed"))

    return app
