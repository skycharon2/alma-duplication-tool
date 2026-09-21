"""Confirmed Archive continuum frequency and direct aggregate RMS comparisons."""
import math

from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.rules.confirmed import DECISION_REF
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionValue, CriterionIssue,
    CriterionOutcome as O, MethodApproval, MethodApplicability as A,
    EvaluationStatus as E, EvidenceSide as S,
)
from alma_duplicate.rules.numeric import positive_canonical, symmetric_factor


def _quantity_issue(value, unit, side, path):
    try:
        if value is None or (value.unit or "").replace(" ", "") != unit:
            raise ValueError()
        positive_canonical(value.value)
    except ValueError:
        return CriterionIssue(side, "MISSING_OR_INVALID_QUANTITY", path,
                              f"A finite positive {unit} quantity is required")
    return None


def _candidate(context, name):
    if not isinstance(context.evidence, ArchiveContextEvidence):
        return None, [CriterionIssue(S.CANDIDATE, "ARCHIVE_SOURCE_REQUIRED", "context", "Queue mapping not approved")]
    e = context.evidence.prepared.comparison_evidence
    q = e.frequency.centre if name == "frequency" else e.continuum_sensitivity.quantity
    value = CriterionValue(q.canonical_value, q.canonical_unit, name,
                           "ARCHIVE_SKY_FREQUENCY" if name == "frequency" else
                           "ARCHIVE_ESTIMATED_AGGREGATE_RMS")
    issues = [] if q.is_available else [CriterionIssue(S.CANDIDATE, q.status.value,
                                                       f"context.{name}", "Archive quantity unavailable")]
    return value, issues


def _result(criterion, context, proposed, candidate, issues, ratio=None, limit=None, details=()):
    outcome = None if issues else (O.SATISFIED if ratio <= positive_canonical(limit) else O.NOT_SATISFIED)
    try:
        numeric = None if ratio is None else float(ratio)
        if numeric is not None and not math.isfinite(numeric):
            numeric = None
    except OverflowError:
        numeric = None
    return CriterionResult(
        criterion_id=criterion, policy_ref=f"{POLICY_DOCUMENT}, Spectral windows",
        method_version=("archive_cont_rms_2" if criterion == "CONT-RMS" else "archive_cont_freq_1"),
        approval=MethodApproval.APPROVED,
        applicability=A.UNRESOLVED if issues else A.APPLICABLE,
        evaluation=E.INSUFFICIENT_INFORMATION if issues else E.EVALUATED,
        outcome=outcome, context_id=context.context_id, proposed=proposed, candidate=candidate,
        issues=tuple(issues), reasons=tuple(i.code for i in issues) if issues else
        ("WITHIN_INCLUSIVE_LIMIT" if outcome is O.SATISFIED else "EXCEEDS_LIMIT",),
        derived=(("factor", numeric), ("max_factor", limit)),
        details=details + (() if ratio is None else (("factor_exact", str(ratio)),)),
        decision_refs=(DECISION_REF,),
    )


def evaluate_continuum_frequency(request, context):
    f = request.representative_frequency
    proposed = None if f is None else CriterionValue(
        f.quantity.value, f.quantity.unit, "representative_frequency", "USER_SETUP_REPRESENTATIVE_SKY")
    candidate, issues = _candidate(context, "frequency")
    if f is not None and f.kind != "SKY":
        issues.append(CriterionIssue(S.PROPOSED, "REPRESENTATIVE_SKY_FREQUENCY_REQUIRED",
                                     "request.representative_frequency.kind", "No REST/mean-window fallback"))
    for value, side, path in ((proposed, S.PROPOSED, "request.representative_frequency"),
                              (candidate, S.CANDIDATE, "context.frequency")):
        issue = _quantity_issue(value, "GHz", side, path)
        if issue:
            issues.append(issue)
    ratio = None if issues else symmetric_factor(proposed.value, candidate.value)
    return _result("CONT-FREQ", context, proposed, candidate, issues, ratio, 1.3)


def evaluate_continuum_rms(request, context):
    candidate, issues = _candidate(context, "cont_sensitivity_bandwidth")
    # Multiple declarations cannot be resolved by selecting the most favourable RMS.
    declarations = [s for s in request.sensitivities if s.purpose == "CONTINUUM"]
    proposed = None
    if len(declarations) != 1:
        issues.append(CriterionIssue(S.PROPOSED, "UNIQUE_AGGREGATE_RMS_REQUIRED",
                                     "request.sensitivities", "Exactly one continuum declaration is required"))
    else:
        s = declarations[0]
        if (s.scope != "SETUP" or s.setup_id != request.setup_id or s.basis != "AGGREGATE"
                or s.aggregate_path != "DIRECT_DECLARATION"):
            issues.append(CriterionIssue(S.PROPOSED, "DIRECT_SETUP_AGGREGATE_RMS_REQUIRED",
                                         "request.sensitivities", "No channel/bandwidth conversion in this method"))
        known_ids = {w.window_id for w in request.spectral_windows}
        if (len(set(s.window_ids)) != len(s.window_ids)
                or not set(s.window_ids) <= known_ids):
            issues.append(CriterionIssue(S.PROPOSED, "INVALID_CONTRIBUTING_WINDOW_REFERENCE",
                                         "request.sensitivities.window_ids",
                                         "Contributing windows must be unique references within this setup"))
        if s.rms is not None:
            proposed = CriterionValue(s.rms.value, s.rms.unit, s.sensitivity_id,
                                      "PROPOSED_REQUESTED_AGGREGATE_RMS")
    for value, side, path in ((proposed, S.PROPOSED, "request.sensitivities"),
                              (candidate, S.CANDIDATE, "context.cont_sensitivity_bandwidth")):
        issue = _quantity_issue(value, "mJy/beam", side, path)
        if issue:
            issues.append(issue)
    ratio = None if issues else positive_canonical(candidate.value) / positive_canonical(proposed.value)
    return _result("CONT-RMS", context, proposed, candidate, issues, ratio, 2.0,
                   tuple(("contributing_window_id", wid) for wid in declarations[0].window_ids)
                   if len(declarations) == 1 else ())
