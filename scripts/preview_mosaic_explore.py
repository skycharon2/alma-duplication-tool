"""Run the fixture-only Mosaic Explore preview on localhost."""
from flask import render_template

from alma_duplicate.ui import create_app


def preview_app():
    app = create_app(dict(AUTO_QUEUE=False, REPORT_DIRECTORY=None, OFFLINE_QUEUE_CSV=None, MANAGED_QUEUE_ROOT=None,
                          LIVE_ARCHIVE=False, LIVE_AQ=False))
    # Screen coordinates and frequencies are illustrative layout fixtures.
    rows = [
        dict(source="Archive", candidate="Example Member A", geometry="Mosaic", array="",
             intent="LINE", shape="region", frequency=101.2, covered=2),
        dict(source="Queue", candidate="Example configuration B", geometry="Custom mosaic", array="7 m",
             intent="Continuum", shape="beams", frequency=101.6, covered=3),
        dict(source="Queue", candidate="Example configuration B", geometry="Custom mosaic", array="12 m",
             intent="Continuum", shape="beams", frequency=101.6, covered=2),
    ]

    @app.get("/preview/mosaic-explore")
    def mosaic_explore_preview():
        return render_template("mosaic_visualization.html", rows=rows)

    return app


if __name__ == "__main__":
    preview_app().run(host="127.0.0.1", port=5052)
