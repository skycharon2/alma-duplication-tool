"""Bind a Queue Single Field beam to a proposed Mosaic pointing list."""
from collections import defaultdict
from dataclasses import asdict

from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.domain.queue import QueueMosaicKind
from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.queue_mosaic import SCHEMA, _center
from alma_duplicate.queue_mosaic_row_science import evaluate_row_candidates
from alma_duplicate.queue_position import candidate_frequency
from alma_duplicate.queue_row_beam import DECISION_REF, resolve_queue_beam_interpretation
from alma_duplicate.rules.queue_mosaic_position import MAX_PAIRS, QueueMosaicCoverage, assess_queue_mosaic_position


def assess_single_field_science(parsed, request, proposed, *, nominal_conversion=None, prepared=None):
    snapshot = parsed.snapshot.snapshot_sha256
    contexts = {}
    groups = defaultdict(list)
    for context in build_queue_contexts(parsed).contexts:
        row = context.evidence.row
        if row.spatial.mosaic_kind is QueueMosaicKind.SINGLE_FIELD:
            contexts[context.reference.raw_row_id] = context
            groups[context.evidence.association.content_fingerprint].append(context)
    beams = {key: resolve_queue_beam_interpretation(members[0].evidence.row)
             for key, members in groups.items()}
    array_count = sum(len(beam.diameters_m) for beam in beams.values())
    if len(proposed['points']) * array_count > MAX_PAIRS:
        raise ValueError('Single Field batch pointing comparison budget exceeded')
    candidates = []
    for fingerprint, members in groups.items():
        context = members[0]
        row = context.evidence.row
        ids = tuple(member.reference.raw_row_id for member in members)
        candidate_id = f'{snapshot}:single:{fingerprint}'
        beam = beams[fingerprint]
        center = _center(row)
        frequency, source, reasons = candidate_frequency(row)
        candidate = dict(candidate_id=candidate_id, source_rows=[dict(source_row_id=i) for i in ids],
            array_inference=asdict(beam), tp_treatment='IGNORED' if row.request.use_tp else 'NOT_REQUESTED',
            geometry=dict(source_row_id=ids[0], center=center, frequency_source=source,
                          frequency_ghz=frequency, frequency_reasons=reasons),
            group=asdict(context.evidence.association.group_key),
            spectral_setup_id=context.evidence.association.spectral_setup_id)
        bindings = []
        invalid = set()
        for diameter in beam.diameters_m:
            if center['icrs_deg'] is None or frequency is None:
                continue
            try:
                if primary_beam_fwhm_deg(frequency, diameter) >= 180:
                    raise ValueError('Beam exceeds hemisphere')
            except ValueError:
                invalid.add(diameter)
                continue
            ra, dec = center['icrs_deg']
            bindings.append(QueueMosaicCoverage(candidate_id, snapshot, ids, diameter, frequency,
                source, (dict(id=ids[0], ra_deg=ra, dec_deg=dec, frame='ICRS'),),
                ids[0], association_confirmed=True, complete=True))
        position = assess_queue_mosaic_position(proposed, dict(schema_version=SCHEMA,
            snapshot_sha256=snapshot, candidates=[candidate]), candidate_id, bindings)
        position['coverage_basis'] = 'QUEUE_SINGLE_FIELD_CENTER_AND_INFERRED_ARRAY'
        for variant in position['beam_variants']:
            if center['icrs_deg'] is None:
                variant['reasons'].extend(center['reasons'])
            if frequency is None:
                variant['reasons'].extend(reasons)
            if variant['diameter_m'] in invalid:
                variant['reasons'].append('CANDIDATE_BEAM_UNREPRESENTABLE')
        candidate['position'] = position
        candidates.append(candidate)
    return evaluate_row_candidates(dict(snapshot_sha256=snapshot, candidates=candidates, summary={}),
        contexts, request, proposed, kind='single_field', decision=DECISION_REF,
        nominal_conversion=nominal_conversion, prepared=prepared)
