"""Flask application factory for the thin browser interface."""

from flask import Flask, Response


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
        return Response(
            "ALMA Duplication Assessment\n",
            mimetype="text/plain",
        )

    return app
