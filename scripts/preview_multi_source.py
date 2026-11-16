"""Serve a reproducible, local-only batch navigation preview using offline data."""
import argparse
from pathlib import Path
from secrets import token_hex

from flask import redirect, session, url_for

from alma_duplicate.ui import create_app
from alma_duplicate.ui.batch_assessment import execute_batch
from alma_duplicate.ui.runs import BrowserAssessment


def preview_app():
    root = Path(__file__).resolve().parents[1]
    archive = root / 'examples/confirmed_line/archive/manifest.json'
    queue = root / 'examples/acceptance/queue/dual-source-line.csv'
    app = create_app(dict(
        AUTO_QUEUE=False, REPORT_DIRECTORY=None, OFFLINE_ARCHIVE_REPLAY=archive,
        OFFLINE_QUEUE_CSV=queue, MANAGED_QUEUE_ROOT=None, ARCHIVE_ARRAY_EVIDENCE=None,
        LIVE_ARCHIVE=False, LIVE_AQ=False, SUBMITTED_LINE_V2_UI_ENABLED=False))
    owner = token_hex(32)
    row = 'w123456abcdef'
    values = dict(
        target_kind='FIXED', geometry='SINGLE_POINTING', setup_id='setup-1',
        sources=['ARCHIVE', 'QUEUE'], intents=['LINE', 'CONTINUUM'], angular='0.3',
        radius_mode='EXPLICIT', radius='30', representative='230.538',
        representative_kind='SKY', aggregate='0.3', continuum_setup_declaration='on',
        normal_form_version='1', **{
            row + '_id': 'line-1', row + '_center': '230.538',
            row + '_center_kind': 'SKY', row + '_mode': 'FDM',
            row + '_resolution': '20', row + '_rms': '0.3'})
    runs = app.extensions['assessment_runs']
    try:
        batch_id = execute_batch(
            values, [row], (root / 'examples/acceptance/batch/targets.csv').read_bytes(),
            runner=BrowserAssessment(archive_replay=str(archive), queue_csv=str(queue)),
            runs=runs, owner=owner, submission_token=token_hex(16))
    except Exception:
        runs.close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()
        raise

    @app.get('/acceptance/batch')
    def acceptance():
        # This local preview intentionally shares one synthetic batch between
        # browsers. Production routes do not contain this session shortcut.
        session['batch_owner'] = owner
        return redirect(url_for('batch.overview', batch_id=batch_id))

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5057)
    args = parser.parse_args()
    app = preview_app()
    print(f'Offline synthetic batch: http://127.0.0.1:{args.port}/acceptance/batch')
    try:
        app.run(host='127.0.0.1', port=args.port, threaded=True, use_reloader=False)
    finally:
        app.extensions['assessment_runs'].close()
        app.extensions['source_uploads'].close()
        app.extensions['mosaic_uploads'].close()
