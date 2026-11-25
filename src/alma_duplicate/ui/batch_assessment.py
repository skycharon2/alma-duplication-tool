"""Bounded multi-source execution using existing browser scientific assessment."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager, nullcontext
from contextvars import copy_context
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import json
import logging
from threading import BoundedSemaphore, Event, RLock
from time import perf_counter

from alma_duplicate.performance import PerformanceRecorder, measure_stage

from alma_duplicate.progress import observe_progress
from alma_duplicate.ui.archive_status import archive_run_status
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.ui.proposed import build_document
from alma_duplicate.ui.run_store import RetentionCapacityError

logger = logging.getLogger(__name__)


def _candidate_outcome_digest(contexts):
    """Hash the multiset of visible candidate identities and decisions."""
    candidates = []
    for context in contexts:
        reference = context.get('reference', {})
        decisions = sorted((b['branch'], b['status'], b['truth'], sorted(b['reasons']))
                           for b in context['branches'])
        identity = (reference.get('source'), reference.get('component_index'),
                    context.get('display_identity', {}))
        candidates.append(json.dumps((identity, decisions), sort_keys=True, separators=(',', ':')))
    return sha256('\n'.join(sorted(candidates)).encode('utf-8')).hexdigest()


def _tap_retrieval_phases(stages):
    fields = {'tap_http_headers': 'headers_seconds', 'tap_http_body_read': 'body_read_seconds',
              'tap_votable': 'votable_overhead_seconds', 'tap_materialize': 'materialize_seconds'}
    by_id = {stage.stage_id: stage for stage in stages}
    totals = Counter()
    for stage in stages:
        if stage.name not in fields:
            continue
        parent = by_id.get(stage.parent_id)
        while parent is not None and parent.name != 'tap_retrieval':
            parent = by_id.get(parent.parent_id)
        if parent is not None:
            totals[fields[stage.name]] += stage.self_wall_seconds
    return {name: round(max(0, seconds), 3) for name, seconds in totals.items()}


class BatchValidationError(ValueError):
    """All preflight results remain available to the future input controller."""

    def __init__(self, preflights):
        super().__init__('Correct batch inputs before running assessments')
        self.preflights = preflights


def execute_batch(values, rows, source_bytes, *, runner, runs, owner, submission_token,
                  format='csv', progress=None, max_workers=1, performance=None, aq_member_workers=2,
                  tap_workers=None):
    """Validate all branches, reserve a manifest, then assess with bounded target concurrency.

    Return the batch ID, including when its branches failed or a concurrent call
    already claimed it. No scientific outcome is inferred from this return value.
    Duplicate protection lasts only as long as the retained manifest.
    """
    if type(max_workers) is not int or not 1 <= max_workers <= 4:
        raise ValueError('Batch workers must be an integer between 1 and 4')
    if tap_workers is None:
        tap_workers = max_workers
    if type(tap_workers) is not int or not 1 <= tap_workers <= 5:
        raise ValueError('Batch TAP workers must be an integer between 1 and 5')
    if type(aq_member_workers) is not int or aq_member_workers not in (1, 2):
        raise ValueError('AQ member workers must be 1 or 2')
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
        submission_token=submission_token, reserve_execution=True, name=values.get('batch_name', ''))
    if not runs.batches.claim_execution(batch_id, owner):
        return batch_id
    total = len(preflight['sources']) * len(purposes)
    source_positions = {child['source']['source_id']: (i + 1, child['source']['name'])
                        for i, child in enumerate(preflight['sources'])}

    progress_lock = RLock()
    completed = 0
    stopped = Event()
    live_archive = configured.archive_kind == 'LIVE' and 'ARCHIVE' in values['sources']
    target_workers = max_workers
    if live_archive and (max_workers > 1 or tap_workers > max_workers):
        target_workers = max(max_workers, min(len(preflight['sources']), max_workers + 1, tap_workers + 1))
    archive_slots = BoundedSemaphore(tap_workers) if live_archive else None
    local_slots = BoundedSemaphore(max_workers) if target_workers > max_workers else None

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

    batch_started = perf_counter()
    notify('batch_started', 0)
    try:
        pinned = configured.pin_queue_for_submission('QUEUE' in values.get('sources', []))
        pinned = replace(pinned, aq_member_workers=aq_member_workers)
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
            tap_started = None
            result = None
            run_id = None
            failure = None
            try:
                with observer, timing.record(), ExitStack() as branch_scope:
                    local_acquired = False

                    def acquire_local_slot():
                        nonlocal local_acquired
                        if local_slots is not None and not local_acquired:
                            with measure_stage('local_slot_wait'):
                                branch_scope.enter_context(local_slots)
                            local_acquired = True

                    @contextmanager
                    def archive_search_slot():
                        nonlocal tap_started
                        try:
                            with ExitStack() as tap_scope:
                                with measure_stage('tap_slot_wait'):
                                    tap_scope.enter_context(archive_slots)
                                if stopped.is_set():
                                    raise RuntimeError('Batch stopped before Archive search')
                                tap_started = perf_counter() - batch_started
                                yield
                        finally:
                            acquire_local_slot()

                    branch_runner = replace(pinned, archive_search_slot=archive_search_slot) if live_archive else pinned
                    result = branch_runner.assess(document)
                    acquire_local_slot()
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
                report = (result.document or {}) if result is not None else {}
                sources = report.get('sources', {})
                archive = archive_run_status(report) or {}
                archive_stages = archive.get('stages', [])
                tap = archive_stages[0] if archive_stages else None
                tap_diagnostic = dict(
                    connection=configured.archive_connection,
                    source_status=sources.get('ARCHIVE', {}).get('status'),
                    region=tap['region'] if tap else None,
                    attempts=[{'region': a['region'], 'status': a['status']} for a in tap['attempts']]
                    if tap else [],
                    retrieval_seconds=round(sum(s.wall_seconds for s in timing.stages
                                                if s.name == 'tap_retrieval'), 3),
                    retrieval_phases=_tap_retrieval_phases(timing.stages),
                )
                logger.info('Batch %s target %s %s archive_tap=%s', batch_id, source_id, purpose,
                            json.dumps(tap_diagnostic))
                logger.info('Batch %s target %s %s wall_seconds=%.3f stages=%s',
                            batch_id, source_id, purpose, perf_counter() - started,
                            [(s.name, round(s.wall_seconds, 3), round(s.thread_cpu_seconds, 3))
                             for s in timing.stages if s.name != 'tap_http_body_read'])
            if performance is not None:
                # Diagnostics cannot change report publication or branch outcomes.
                try:
                    aq = (sources.get('ARCHIVE', {}).get('array_evidence') or {}).get('acquisition') or {}
                    contexts = report.get('context_evaluations', [])
                    outcomes = Counter(f"{branch['branch']}:{branch['status']}"
                                       for context in contexts for branch in context['branches'])
                    performance(dict(source_id=source_id, purpose=purpose, run_id=run_id,
                        wall_seconds=perf_counter() - started, error_type=failure,
                        assessment_status=str(result.status) if result is not None else None,
                        sources={k: v['status'] for k, v in sources.items()}, aq_status=aq.get('status'),
                        archive_tap=tap_diagnostic,
                        tap_start_seconds_from_batch_start=tap_started,
                        aq_members=tuple(query['member_ous_uid'] for query in aq.get('queries', [])),
                        retained_contexts=len(contexts), branch_outcomes=dict(outcomes),
                        candidate_outcome_sha256=_candidate_outcome_digest(contexts) if report else None,
                        stages=[asdict(s) for s in timing.stages]))
                except Exception:
                    logger.warning('Batch performance observer failed', exc_info=True)
            with progress_lock:
                completed += 1
                notify('batch_branch_finished', source_id=source_id, purpose=purpose)

    if target_workers == 1:
        for index, child in enumerate(preflight['sources']):
            assess_target(index, child)
    else:
        with ThreadPoolExecutor(max_workers=target_workers,
                                thread_name_prefix='batch-target') as executor:
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
