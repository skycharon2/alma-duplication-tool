"""TP is retained as provenance, never a duplication branch or uncertainty.

Only positively identified TP-only Archive evidence is excluded. Missing or
conflicting array evidence remains unresolved for the interferometric workflow.
"""
from alma_duplicate.parsers.array_classification import classify_array_type


def archive_tp_only(context, evidence=None):
    if context.reference.source != 'ARCHIVE':
        return False
    if evidence is not None:
        if (evidence.context_id != context.context_id
                or evidence.source_record_id != context.reference.source_record_id):
            raise ValueError('Array evidence belongs to another candidate')
        return getattr(evidence, 'components', ()) == ('TOTAL_POWER',) and not evidence.diameters_m
    array = classify_array_type(context.evidence.prepared.raw_row.get('antenna_arrays'))
    families = set(dict(array.family_counts)) or {array.family}
    return families == {'TOTAL_POWER'} and not array.unrecognized_tokens


def ignored_mosaic(context):
    return dict(context_id=context.context_id, criteria=(), request_criteria=(),
                branches=(), line_pairing=None, line_pairs=(),
                coverage=dict(scope_status='IGNORED_TP', tp_treatment='IGNORED',
                              reasons=['TP_IGNORED_FOR_DUPLICATION']))
