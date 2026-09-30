"""Flask application factory for the thin browser interface."""

import os

from flask import Flask, Response, abort, redirect, render_template, request, url_for

from alma_duplicate.ui.reports import load_reports
from alma_duplicate.ui.proposed import MAX_WINDOWS, contributing_windows, initial_form, new_row, read_form, validate_form
from alma_duplicate.reporting import report_json_text


def create_app(config=None):
    """Create the browser application without accessing assessment sources."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    app.config["REPORT_DIRECTORY"] = os.environ.get("ALMA_UI_REPORT_DIR")
    if config is not None:
        app.config.from_mapping(config)

    reports = load_reports(app.config["REPORT_DIRECTORY"])

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

    @app.get("/reports/<report_id>")
    def report_view(report_id):
        item = artifact(report_id)
        page = request.args.get("page", "1")
        if not page.isdecimal() or len(page) > 8 or int(page) < 1:
            abort(400)
        page = int(page)
        contexts = item.document["context_evaluations"]
        pages = max(1, (len(contexts) + 19) // 20)
        if page > pages:
            abort(404)
        start = (page - 1) * 20
        return render_template("report.html", item=item, report_id=report_id,
                               document=item.document, contexts=contexts[start:start + 20],
                               start=start, page=page, pages=pages)

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
        if request.method == "POST":
            try:
                values, rows = read_form(request.form)
            except ValueError as exc:
                abort(400, description=str(exc))
            action = values.get("action", "validate")
            if action == "add":
                if len(rows) >= MAX_WINDOWS:
                    abort(400, description="Maximum 32 windows in this form")
                rows.append(new_row())
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
            elif action in {"validate", "download"}:
                document, result, issues = validate_form(values, rows)
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
                               pending_removal=pending_removal, edit_notice=edit_notice)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return redirect(url_for("proposed"))

    return app
