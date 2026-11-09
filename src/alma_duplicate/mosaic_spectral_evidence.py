"""Attach *display-only*, source-bound spectral setup evidence to Mosaic reports.

This does not evaluate or modify criteria. Old reports without these optional
fields remain readable; absence must never be filled with estimated intervals.
"""
from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.queue import RegularSpwEvidence
from alma_duplicate.reporting import json_value, _display_identity


def attach_archive_spectral_setups(evaluated, contexts):
    """Build candidate-level, context-keyed *display* evidence without mutation.

    Captured Archive scientific ``evaluation.contexts`` are an exact historical
    acceptance contract. Never inject visualization fields into those records.
    A candidate-level sidecar retains the exact raw-row binding instead.
    """
    by_id = {context.context_id: context for context in contexts}
    displays = {}
    for result in evaluated.get('contexts', []):
        if not any(branch.get('status') == 'CRITERIA_MET'
                   for branch in result.get('branches', [])):
            continue
        context = by_id.get(result.get('context_id'))
        if context is None or not isinstance(context.evidence, ArchiveContextEvidence):
            continue
        support = context.evidence.support_evidence
        if support is None or support.raw_row_id != context.reference.raw_row_id:
            continue
        displays[context.context_id] = {
            'spectral_setup_display': json_value({
                'reference': context.reference, 'evidence': support}),
            'source_reference': json_value(context.reference),
            'display_identity': json_value(_display_identity(context)),
        }
    return displays


def attach_queue_spectral_setups(report, parsed):
    """Persist actual parsed regular-SPW SKY bounds for matching Queue candidates.

    Geometry-agnostic: Custom, Rectangle and Single Field all have one source-row
    representative. For Custom, every grouped row must agree in spectral evidence.
    SPS/spectral scans are intentionally not expanded into fictional windows.
    """
    snapshot = parsed.snapshot.snapshot_sha256
    indexed = {row.raw_row.row_id.value: row for row in parsed.row_inputs}
    for candidate in report.get('candidates', []):
        science = candidate.get('science') or {}
        if not any(branch.get('truth') == 'TRUE' for variant in science.get('variants', [])
                   for branch in variant.get('branches', [])):
            continue
        ids = [r.get('source_row_id') for r in candidate.get('source_rows', [])]
        representative = (science.get('representative_source_row_id') or
                          science.get('source_row_id'))
        if not ids or representative not in ids or any(key not in indexed for key in ids):
            continue
        spectral = indexed[representative].spectral
        if (not isinstance(spectral, RegularSpwEvidence) or
                any(indexed[key].spectral != spectral for key in ids)):
            continue
        science['spectral_setup_display'] = {
            'schema_version': 'mosaic_queue_regular_spws_display_1',
            'candidate_id': candidate['candidate_id'],
            'snapshot_sha256': snapshot,
            'source_row_ids': ids,
            'representative_source_row_id': representative,
            'spectral_setup_id': indexed[representative].raw_row.row_id.value,
            'spws': [{
                'number': spw.number,
                'nominal_low_ghz': spw.lower_sky_frequency_ghz,
                'nominal_high_ghz': spw.upper_sky_frequency_ghz,
                'usable_low_ghz': spw.usable_lower_sky_frequency_ghz,
                'usable_high_ghz': spw.usable_upper_sky_frequency_ghz,
            } for spw in spectral.spws],
        }
    return report
