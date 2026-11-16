"""Serial multi-source execution using existing browser scientific assessment."""
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
import logging

from alma_duplicate.progress import observe_progress
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.proposed import build_document

logger = logging.getLogger(__name__)


class BatchValidationError(ValueError):
    """All preflight results remain available to the future input controller."""

    def __init__(self, preflights):
        super().__init__('Correct batch inputs before running assessments')
        self.preflights = preflights


def execute_batch(values, rows, source_bytes, *, runner, runs, owner, submission_token,
                  format='csv', progress=None):
    """Validate all branches, reserve a manifest, then assess serially.

    Return the batch ID, including when its branches failed or a concurrent call
    already claimed it. No scientific outcome is inferred from this return value.
    Duplicate protection lasts only as long as the retained manifest.
    """
    if submission_token is None:
        raise ValueError('A submission token is required')
    values, rows = deepcopy(values), list(rows)
    preflight = prepare_batch_form(values, rows, source_bytes, format=format, require_line_complete=True)
    purposes = [p for p in ('LINE', 'CONTINUUM') if p in values.get('intents', [])]
    preflights = {'combined': preflight}
    for purpose in purposes:
        preflights[purpose] = prepare_batch_form(
            values | {'intents': [purpose]}, rows, source_bytes, format=format, require_line_complete=True)
    if not purposes or any(not p['is_valid'] or not p['can_search'] for p in preflights.values()):
        raise BatchValidationError(preflights)
    configured = replace(runner, archive_connection=values.get('archive_connection', 'AUTO'))
    if not configured.enabled:
        raise ValueError('Assessment sources are not configured')
    shared, _ = build_document(values, rows)
    batch_id = runs.batches.create(owner, dict(document=shared, archive_connection=configured.archive_connection),
        [c['source'] for c in preflight['sources']], preflight['input_sha256'], purposes,
        submission_token=submission_token, reserve_execution=True)
    if not runs.batches.claim_execution(batch_id, owner):
        return batch_id
    total = len(preflight['sources']) * len(purposes)

    def notify(stage, completed, *, source_id=None, purpose=None, event=None):
        if progress is not None:
            try:
                progress(dict(event or {}, stage=stage, batch_id=batch_id,
                              source_id=source_id, purpose=purpose,
                              batch_completed=completed, batch_total=total))
            except Exception:
                # Progress reporting must not affect execution or saved science.
                logger.warning('Batch progress observer failed', exc_info=True)

    notify('batch_started', 0)
    try:
        pinned = configured.pin_queue_for_submission('QUEUE' in values.get('sources', []))
    except Exception:
        logger.exception('Batch source setup failed for %s', batch_id)
        for child in preflight['sources']:
            for purpose in purposes:
                runs.batches.update(batch_id, owner, child['source']['source_id'], purpose,
                                    'FAILED', error='Source setup failed. Inspect server logs.')
        notify('batch_finished', total)
        return batch_id

    completed = 0
    for index, child in enumerate(preflight['sources']):
        source_id = child['source']['source_id']
        for purpose in purposes:
            document = preflights[purpose]['sources'][index]['document']
            runs.batches.update(batch_id, owner, source_id, purpose, 'RUNNING')
            notify('batch_branch_started', completed, source_id=source_id, purpose=purpose)
            observer = (observe_progress(lambda event: notify(event['stage'], completed,
                        source_id=source_id, purpose=purpose, event=event)) if progress else nullcontext())
            try:
                with observer:
                    result = pinned.assess(document)
                    if result.document is None:
                        raise ValueError('Assessment returned no report')
                    run_id = runs.add(document, result)
                    runs.batches.update(batch_id, owner, source_id, purpose, 'COMPLETED', run_id=run_id)
            except Exception:
                logger.exception('Batch branch failed: %s / %s / %s', batch_id, source_id, purpose)
                # Expired/closed parent or inability to record failure propagates:
                # never continue source queries without an accountable manifest.
                runs.batches.update(batch_id, owner, source_id, purpose, 'FAILED',
                                    error='Assessment or report storage failed. Inspect server logs.')
            completed += 1
            notify('batch_branch_finished', completed, source_id=source_id, purpose=purpose)
    notify('batch_finished', completed)
    return batch_id
