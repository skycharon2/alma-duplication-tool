"""Bounded multi-source execution using existing browser scientific assessment."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from contextvars import copy_context
from copy import deepcopy
from dataclasses import asdict, replace
import logging
from threading import Event, RLock
from time import perf_counter

from alma_duplicate.performance import PerformanceRecorder

from alma_duplicate.progress import observe_progress
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.proposed import build_document
from alma_duplicate.ui.run_store import RetentionCapacityError

logger = logging.getLogger(__name__)


class BatchValidationError(ValueError):
    """All preflight results remain available to the future input controller."""

    def __init__(self, preflights):
        super().__init__('Correct batch inputs before running assessments')
        self.preflights = preflights


def execute_batch(values, rows, source_bytes, *, runner, runs, owner, submission_token,
                  format='csv', progress=None, max_workers=1, performance=None):
    """Validate all branches, reserve a manifest, then assess with bounded target concurrency.

    Return the batch ID, including when its branches failed or a concurrent call
    already claimed it. No scientific outcome is inferred from this return value.
    Duplicate protection lasts only as long as the retained manifest.
    """
    if type(max_workers) is not int or not 1 <= max_workers <= 4:
        raise ValueError('Batch workers must be an integer between 1 and 4')
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
    source_positions = {child['source']['source_id']: (i + 1, child['source']['name'])
                        for i, child in enumerate(preflight['sources'])}

    progress_lock = RLock()
    completed = 0
    stopped = Event()

    def notify(stage, count=None, *, source_id=None, purpose=None, event=None):
        with progress_lock:
            publish(stage, completed if count is None else count, source_id=source_id, purpose=purpose, event=event)

    def publish(stage, count, *, source_id=None, purpose=None, event=None):
        if progress is not None:
            try:
                progress(dict(event or {}, stage=stage, batch_id=batch_id,
                              source_id=source_id, purpose=purpose,
                              source_position=source_positions.get(source_id, (None, None))[0],
                              source_name=source_positions.get(source_id, (None, None))[1],
                              source_total=len(preflight['sources']),
                              batch_completed=count, batch_total=total, batch_workers=max_workers))
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

    def assess_target(index, child):
        try:
            assess_branches(index, child)
        except Exception:
            stopped.set()
            raise

    def assess_branches(index, child):
        nonlocal completed
        source_id = child['source']['source_id']
        for purpose in purposes:
            if stopped.is_set():
                return
            document = preflights[purpose]['sources'][index]['document']
            runs.batches.update(batch_id, owner, source_id, purpose, 'RUNNING')
            notify('batch_branch_started', source_id=source_id, purpose=purpose)
            observer = (observe_progress(lambda event: notify(event['stage'],
                        source_id=source_id, purpose=purpose, event=event)) if progress else nullcontext())
            timing = PerformanceRecorder()
            started = perf_counter()
            result = None
            run_id = None
            failure = None
            try:
                with observer, timing.record():
                    result = pinned.assess(document)
                    if result.document is None:
                        raise ValueError('Assessment returned no report')
                    run_id = runs.add(document, result, protect=True)
                    runs.batches.update(batch_id, owner, source_id, purpose, 'COMPLETED', run_id=run_id)
            except Exception as exc:
                failure = type(exc).__name__
                logger.exception('Batch branch failed: %s / %s / %s', batch_id, source_id, purpose)
                # Expired/closed parent or inability to record failure propagates:
                # never continue source queries without an accountable manifest.
                runs.batches.update(batch_id, owner, source_id, purpose, 'FAILED',
                                    error=('Report not saved: storage capacity limit reached. Earlier batch reports remain protected.'
                                           if isinstance(exc, RetentionCapacityError) else
                                           'Assessment or report storage failed. Inspect server logs.'))
            finally:
                logger.info('Batch %s target %s %s wall_seconds=%.3f stages=%s',
                            batch_id, source_id, purpose, perf_counter() - started,
                            [(s.name, round(s.wall_seconds, 3), round(s.thread_cpu_seconds, 3))
                             for s in timing.stages])
            if performance is not None:
                # Diagnostics cannot change report publication or branch outcomes.
                try:
                    performance(dict(source_id=source_id, purpose=purpose, run_id=run_id,
                        wall_seconds=perf_counter() - started, error_type=failure,
                        assessment_status=str(result.status) if result is not None else None,
                        sources={k: v['status'] for k, v in result.document['sources'].items()}
                            if result is not None and result.document is not None else {},
                        stages=[asdict(s) for s in timing.stages]))
                except Exception:
                    logger.warning('Batch performance observer failed', exc_info=True)
            with progress_lock:
                completed += 1
                notify('batch_branch_finished', source_id=source_id, purpose=purpose)

    if max_workers == 1:
        for index, child in enumerate(preflight['sources']):
            assess_target(index, child)
    else:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='batch-target') as executor:
            futures = [executor.submit(copy_context().run, assess_target, index, child)
                       for index, child in enumerate(preflight['sources'])]
            try:
                for future in futures:
                    future.result()
            finally:
                if stopped.is_set():
                    for future in futures:
                        future.cancel()
    notify('batch_finished', completed)
    return batch_id
