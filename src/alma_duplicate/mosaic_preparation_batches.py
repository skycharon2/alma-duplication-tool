"""Checkpoint bounded candidate preparation without dropping unprocessed identities."""
from dataclasses import asdict
from hashlib import sha256
import json
import time
from pathlib import Path

from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits


def _write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def prepare_batches(discovery, *, output, cache, max_candidates, resume, worker, worker_kwargs):
    rows = discovery.get('candidates')
    if discovery.get('schema_version') != 'mosaic_candidate_discovery_1' or not isinstance(rows, list):
        raise ValueError('Expected candidate discovery report')
    if len(rows) > 10000:
        raise ValueError('At most 10000 discovered candidates per run')
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100:
        raise ValueError('Per-invocation candidate budget must be in 1..100')
    keys = [(r['member_ous_uid'], r['source_name']) for r in rows]
    if len(set(keys)) != len(keys) or any(not isinstance(v, str) or not v.strip() for k in keys for v in k):
        raise ValueError('Invalid or duplicate candidate identity')
    limits = worker_kwargs.get('resource_limits') or MosaicResourceLimits()
    if not isinstance(limits, MosaicResourceLimits):
        raise ValueError('Expected MosaicResourceLimits')
    binding = dict(discovery=discovery, cache=str(Path(cache).resolve()), limits=asdict(limits),
                   offline=worker_kwargs.get('offline', False))
    fingerprint = sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    output = Path(output)
    checkpoint = output / 'batch-checkpoint.json'
    if resume:
        state = json.loads(checkpoint.read_text())
        if state['fingerprint'] != fingerprint:
            raise ValueError('Resume discovery, cache, mode or resource limits changed')
    else:
        output.mkdir(parents=True, exist_ok=False)
        _write(output / 'discovery.json', discovery)
        state = dict(fingerprint=fingerprint, completed=[])
        _write(checkpoint, state)
    results = []
    for entry in state['completed']:
        index = len(results)
        expected = f'candidate-{index:05d}/preparation.json'
        if entry['file'] != expected:
            raise ValueError('Unexpected checkpoint receipt path')
        raw = (output / expected).read_bytes()
        if sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Checkpoint receipt integrity mismatch')
        report = json.loads(raw)
        if len(report['candidates']) != 1:
            raise ValueError('Expected one candidate receipt')
        result = report['candidates'][0]
        if index >= len(keys) or (result['member_ous_uid'], result['source_name']) != keys[index]:
            raise ValueError('Checkpoint candidate identity mismatch')
        results.append(result)
    start = len(results)
    for index in range(start, min(len(rows), start + max_candidates)):
        directory = output / f'candidate-{index:05d}'
        if directory.exists():
            raise ValueError('Uncheckpointed candidate directory exists; preserve it and use a new run')
        part = dict(discovery, candidates=[rows[index]])
        started = time.monotonic()
        report = worker(part, output=directory, cache=cache, **worker_kwargs)
        elapsed = time.monotonic() - started
        for candidate in report['candidates']:
            candidate['preparation_elapsed_seconds'] = round(elapsed, 6)
        receipt = directory / 'preparation.json'
        _write(receipt, report)
        results.extend(report['candidates'])
        state['completed'].append(dict(file=str(receipt.relative_to(output)),
                                       sha256=sha256(receipt.read_bytes()).hexdigest()))
        _write(checkpoint, state)
    pending = [dict(context_id=r['context_id'], member_ous_uid=r['member_ous_uid'],
                    source_name=r['source_name'], status='PENDING', stage='NOT_STARTED',
                    policy_status='NOT_EVALUATED') for r in rows[len(results):]]
    success = lambda r: (r['status'] == 'POINTINGS_PREPARED' and r.get('readiness_status') == 'EVIDENCE_BOUND') or (r['status'] == 'METADATA_ONLY_PREPARED' and r.get('readiness_status') == 'ARRAY_ACQUIRED')
    report = dict(schema_version='mosaic_candidate_preparation_1', candidates=results + pending,
        resource_limits=asdict(limits), status='COMPLETED' if not pending and all(map(success, results)) else 'INCOMPLETE',
        discovered_count=len(rows), attempted_count=len(results), pending_count=len(pending),
        failed_or_unready_count=sum(not success(r) for r in results),
        prepared_count=sum(success(r) for r in results),
        reused_package_count=sum(r.get('reused_cache') is True for r in results),
        measured_candidate_count=sum('preparation_elapsed_seconds' in r for r in results),
        measured_candidate_seconds=sum(r.get('preparation_elapsed_seconds', 0) for r in results),
        invocation_candidate_budget=max_candidates,
        invocation_download_upper_bound_bytes=max_candidates * limits.max_download_bytes,
        discovery_status=discovery.get('status'),
        discovery_scope=discovery.get('plan', {}).get('scope'),
        discovery_recall_status=discovery.get('plan', {}).get('recall_status'),
        scope='POINTING_AND_ARRAY_READINESS_NOT_SPECTRAL_SELECTION', policy_status='NOT_EVALUATED')
    _write(output / 'preparation.json', report)
    return report
