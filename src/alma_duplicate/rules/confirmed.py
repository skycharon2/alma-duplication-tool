"""Versioned project decisions; legacy evaluators keep their original approval."""
from dataclasses import replace

from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.rules.model import MethodApproval

DECISION_REF = "docs/evidence/supervisor_confirmation_2026-09-17.md#confirmed-2026-09-21"


def archive_scope(request, context):
    return (isinstance(context.evidence, ArchiveContextEvidence)
            and request.target_kind == "FIXED"
            and request.geometry == "SINGLE_POINTING")


def approve_angular(result, request, context):
    if not archive_scope(request, context):
        return result
    return replace(result, method_version="archive_angular_factor_3",
                   approval=MethodApproval.APPROVED,
                   decision_refs=result.decision_refs + (DECISION_REF,))


def approve_setup(result, *, nominal_conversion):
    # Arbitrary nominal conversion remains provisional, even when selected explicitly.
    if nominal_conversion is not None:
        return result
    return replace(result, method_version="continuum_setup_3",
                   approval=MethodApproval.APPROVED,
                   decision_refs=result.decision_refs + (DECISION_REF,))
