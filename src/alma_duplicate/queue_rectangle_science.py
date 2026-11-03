"""Source-row-bound Rectangle science using existing Appendix A numerics.

All conclusions are conditional on the provisional geometry/array model.
Requested RMS is compared without overlap gain or per-pointing conversion.
"""
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.queue_rectangle_backend import assess_queue_rectangle_csv
from alma_duplicate.queue_mosaic_row_science import evaluate_row_candidates

DECISION = 'docs/queue_rectangle_grid.md#scientific-assessment'


def assess_queue_rectangle_science(parsed, request, proposed, *, candidate_id=None,
                                   nominal_conversion=None, prepared=None):
    """One row and one array per complete AND, then complete array-branch OR."""
    if prepared is not None:
        from alma_duplicate.rules.submitted_line_evaluation import PreparedSubmittedLineRequest
        if not isinstance(prepared, PreparedSubmittedLineRequest) or prepared.line_request is not request:
            raise ValueError('Prepared request must own these scientific operands')
    request.require_implemented_line_scope()
    if request.target_kind != 'FIXED' or request.geometry != 'MOSAIC':
        raise ValueError('Fixed Mosaic scientific request required')
    if not request.intents or any(i not in ('CONTINUUM', 'LINE') for i in request.intents):
        raise ValueError('Select CONTINUUM and/or LINE science')
    if (not isinstance(proposed, dict) or not request.target_name or
        proposed.get('source_name') != request.target_name or proposed.get('setup_id') != request.setup_id):
        raise ValueError('Proposed pointing list must bind to request target and setup')
    report = assess_queue_rectangle_csv(parsed, proposed, candidate_id=candidate_id)
    contexts = {c.reference.raw_row_id: c for c in build_queue_contexts(parsed).contexts}
    return evaluate_row_candidates(report, contexts, request, proposed, kind='rectangle',
        decision=DECISION, nominal_conversion=nominal_conversion, prepared=prepared)
