"""Flask application factory for the thin browser interface."""

from flask import Flask, render_template


def create_app(config=None):
    """Create the browser application without accessing assessment sources."""
    app = Flask(__name__)
    if config is not None:
        app.config.from_mapping(config)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
