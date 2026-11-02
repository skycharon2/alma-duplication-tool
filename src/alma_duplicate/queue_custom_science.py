"""Complete Custom CSV branches under the explicitly selected provisional model.

Single-point numerical rules are reused. Each array ANDs its own position and
science criteria before complete branches are ORed. No cross-array/SPW borrowing.
"""
from dataclasses import asdict, replace

from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.domain.queue import RegularSpwEvidence
from alma_duplicate.reporting import json_value
from alma_duplicate.queue_custom_backend import assess_queue_custom_csv, PROFILE
from alma_duplicate.queue_line_pairing import build_queue_line_pairs
from alma_duplicate.rules.aggregation import (
    BranchAssessment, Truth, aggregate_continuum, criterion_truth, three_and, three_or, CONTINUUM_CRITERIA,
)
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.confirmed import approve_setup
from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup
from alma_duplicate.rules.model import (
    POLICY_DOCUMENT, CriterionResult, CriterionOutcome as O, EvaluationStatus as E,
    MethodApplicability as A, MethodApproval, CriterionIssue, EvidenceSide,
)
from alma_duplicate.rules.queue_continuum import evaluate_queue_continuum
from alma_duplicate.rules.queue_line import evaluate_queue_line_numerical, LINE_CRITERIA, STATUS

DECISION = "docs/queue_custom_science.md#model-scope"
MAX_SPECTRAL_PAIRS = 100_000
REQUIRED = {"CONTINUUM": ("POS-MOSAIC", *CONTINUUM_CRITERIA[1:]),
            "LINE": ("POS-MOSAIC", *LINE_CRITERIA[1:])}


def _common(request, context, position):
    supported = isinstance(context.evidence.row.spectral, RegularSpwEvidence)
    details = (("common_scope", "SUPPORTED_CUSTOM" if supported else "UNRESOLVED"),
               ("csv_profile", PROFILE), ("association_basis", "PROVISIONAL_CSV_CONVENTIONS"),
               ("array_scope", "ROW_BEAM_HYPOTHESIS_NOT_MEASURED_ARRAY_METADATA"))
    # APPROVED here adopts the calculation within this selected model only. The
    # report remains PROVISIONAL, not independent validation of Queue ownership.
    angular = replace(evaluate_angular_resolution(request, context),
        method_version="queue_custom_angular_1", approval=MethodApproval.APPROVED,
        decision_refs=(DECISION,), details=details)
    outcome = None if position["outcome"] == "UNKNOWN" else O(position["outcome"])
    reasons = tuple(position["reasons"])
    if outcome is None and not reasons:
        reasons = ("CUSTOM_POSITION_UNRESOLVED",)
    spatial = CriterionResult(criterion_id="POS-MOSAIC", policy_ref=f"{POLICY_DOCUMENT}, Position",
        method_version="queue_custom_position_1", approval=MethodApproval.APPROVED,
        applicability=A.APPLICABLE if outcome is not None else A.UNRESOLVED,
        evaluation=E.EVALUATED if outcome is not None else E.INSUFFICIENT_INFORMATION,
        outcome=outcome, context_id=context.context_id, proposed=None, candidate=None,
        reasons=reasons, details=details, decision_refs=(DECISION,),
        issues=() if outcome is not None else tuple(CriterionIssue(EvidenceSide.CANDIDATE, reason,
            "custom.position", reason) for reason in reasons),
        derived=(("antenna_diameter_m", position["diameter_m"]),
                 ("covered_fraction_lower", position["covered_fraction_lower"]),
                 ("covered_fraction_upper", position["covered_fraction_upper"])),
        numeric_method="SPHERICAL_EXPLICIT_BOUNDARY_INTEGER_MAJORITY")
    return angular, spatial


def _rms_basis(criterion, proposed):
    """Never promote combined-image RMS to per-pointing RMS or add overlap gain."""
    basis = proposed.get("sensitivity_basis", "PER_POINTING")
    details = criterion.details + (("candidate_mosaic_rms_basis", "CUSTOM_PER_POINTING_REQUEST"),
        ("proposed_mosaic_rms_basis", str(basis)),
        ("mosaic_overlap_gain", "NONE"))
    if basis == "PER_POINTING":
        return replace(criterion, details=details)
    reason = "PROPOSED_MOSAIC_PER_POINTING_RMS_REQUIRED"
    return replace(criterion, outcome=None, applicability=A.UNRESOLVED,
        evaluation=E.INSUFFICIENT_INFORMATION, details=details,
        reasons=criterion.reasons+(reason,), issues=criterion.issues+(
            CriterionIssue(EvidenceSide.PROPOSED, reason, "proposed.sensitivity_basis", reason),))


def _line_branch(request, context, common, proposed, *, submitted_scope=False):
    pairing = build_queue_line_pairs(request, context, mosaic=True)
    if submitted_scope:
        pairing = replace(pairing, proposed_enumeration_complete=True,
            reasons=tuple(r for r in pairing.reasons if r != "PROPOSED_ENUMERATION_INCOMPLETE"),
            builder_version="queue_custom_submitted_line_pair_builder_1",
            scope="ONE_CUSTOM_GROUP_SUBMITTED_REQUIREMENTS_X_REGULAR_SPWS")
    pairs = []
    for attempt in pairing.attempts:
        numerical = tuple(_rms_basis(r, proposed) if r.criterion_id == "LINE-RMS" else r
                          for r in evaluate_queue_line_numerical(request, context, attempt))
        criteria = (common[1], common[0], *numerical)
        truth = three_and(criterion_truth(c) for c in criteria)
        pairs.append(dict(reference=asdict(attempt.reference), criteria=[asdict(c) for c in criteria],
                          truth=truth, status=STATUS[truth], preparation_reasons=list(attempt.reasons)))
    values = [p["truth"] for p in pairs]
    reasons = list(pairing.reasons)
    if not pairing.proposed_enumeration_complete or not pairing.candidate_enumeration_complete:
        values.append(Truth.UNKNOWN)
    truth = three_or(values)
    required = ("POS-MOSAIC", *LINE_CRITERIA[1:])
    branch = BranchAssessment("LINE", context.context_id, STATUS[truth], truth, required,
        tuple(reasons), method_version="queue_custom_line_pair_or_1", decision_refs=(DECISION,),
        scope="ONE_CUSTOM_GROUP_SAME_ARRAY_COMPLETE_PAIRS_ONLY")
    return branch, pairs, pairing


def aggregate_custom_arrays(context_id, expected_diameters, variants):
    """Validate complete branch scope before reusing the existing three-valued OR."""
    if tuple(expected_diameters) not in ((), (7.,), (12.,), (7., 12.)):
        raise ValueError("Invalid inferred Custom array branches")
    if tuple(v["diameter_m"] for v in variants) != tuple(expected_diameters):
        raise ValueError("Custom variants disagree with inferred arrays")
    if not variants:
        return ()
    first = variants[0]["branches"]
    signature = tuple((b.branch, b.required_criteria) for b in first)
    if (not first or any(b.required_criteria != REQUIRED.get(b.branch) for b in first)
        or len({b.branch for b in first}) != len(first) or any(
        tuple((b.branch, b.required_criteria) for b in v["branches"]) != signature
        or any(b.context_id != context_id for b in v["branches"]) for v in variants
    )):
        raise ValueError("Custom array branches must share source context and required criteria")
    result = []
    for i, branch in enumerate(first):
        truth = three_or(v["branches"][i].truth for v in variants)
        result.append(replace(branch, truth=truth, status=STATUS[truth],
            reasons=("COMPLETE_ARRAY_BRANCHES_OR",), method_version="queue_custom_array_or_1",
            scope="SAME_CUSTOM_CANDIDATE_COMPLETE_ARRAY_BRANCHES_ONLY"))
    return tuple(result)


def custom_object_results(candidates):
    """Roll up complete setup/array results per project and target in one snapshot."""
    objects = {}
    for c in candidates:
        group = c["group"]
        key = (group["project_code"], group["target_name"])
        obj = objects.setdefault(key, dict(project_code=key[0], target_name=key[1],
            candidate_ids=[], truth_by_intent={}, matching_arrays_by_intent={}))
        obj["candidate_ids"].append(c["candidate_id"])
        for branch in c["science"]["branches"]:
            intent = branch["branch"]
            previous = obj["truth_by_intent"].get(intent)
            truth = Truth(branch["truth"])
            obj["truth_by_intent"][intent] = (truth if previous is None else three_or((previous, truth)))
            arrays = obj["matching_arrays_by_intent"].get(intent, [])
            obj["matching_arrays_by_intent"][intent] = sorted(set(arrays).union(
                c["science"]["matching_arrays_by_intent"][intent]))
    return list(objects.values())


def assess_queue_custom_science(parsed, request, proposed, *, candidate_id=None, nominal_conversion=None, prepared=None):
    """Validated fixed Mosaic request plus caller point list; no OT runtime input.

    A source-row representative supplies unchanged scalar/spectral operands only
    after all grouped rows have equal typed spectra and requested performance.
    Original row identity stays attached to every SPW pair and the group retains
    every pointing row. No scientific evidence crosses candidate groups.
    """
    if prepared is not None:
        from alma_duplicate.rules.submitted_line_evaluation import PreparedSubmittedLineRequest
        if not isinstance(prepared, PreparedSubmittedLineRequest) or prepared.line_request is not request:
            raise ValueError("Prepared request must own these scientific operands")
    request.require_implemented_line_scope()
    if request.target_kind != "FIXED" or request.geometry != "MOSAIC":
        raise ValueError("Fixed Mosaic scientific request required")
    if not request.intents or any(i not in ("CONTINUUM", "LINE") for i in request.intents):
        raise ValueError("Select CONTINUUM and/or LINE science")
    if (not isinstance(proposed, dict) or not request.target_name
            or proposed.get("source_name") != request.target_name
            or proposed.get("setup_id") != request.setup_id):
        raise ValueError("Proposed pointing list must bind to request target and setup")
    report = assess_queue_custom_csv(parsed, proposed, candidate_id=candidate_id)
    contexts = {c.reference.raw_row_id: c for c in build_queue_contexts(parsed).contexts}
    continuum_request = (prepared.continuum_request if prepared is not None else
                         request if "CONTINUUM" in request.intents else None)
    setup = (approve_setup(evaluate_continuum_setup(continuum_request, nominal_conversion=nominal_conversion),
                           nominal_conversion=nominal_conversion) if continuum_request is not None else None)
    work = sum(len(contexts[c["source_rows"][0]["source_row_id"]].evidence.row.spectral.spws)
               * len(request.spectral_windows)*len(c["position"]["beam_variants"])
               for c in report["candidates"]
               if isinstance(contexts[c["source_rows"][0]["source_row_id"]].evidence.row.spectral, RegularSpwEvidence))
    if work > MAX_SPECTRAL_PAIRS:
        raise ValueError("Custom science spectral pair budget exceeded")
    for candidate in report["candidates"]:
        row_contexts = [contexts[r["source_row_id"]] for r in candidate["source_rows"]]
        first = row_contexts[0]
        if any(c.evidence.row.spectral != first.evidence.row.spectral
               or c.evidence.row.request != first.evidence.row.request for c in row_contexts):
            raise ValueError("Custom group has conflicting spectral/performance operands")
        context = replace(first, context_id=f"QUEUE-CUSTOM:{candidate['candidate_id']}")
        variants = []
        for position in candidate["position"]["beam_variants"]:
            common = _common(request, context, position)
            criteria, branches, pairs, pairing = list(common), [], [], None
            if setup is not None:
                continuum = tuple(_rms_basis(r, proposed) if r.criterion_id == "CONT-RMS" else r
                    for r in evaluate_queue_continuum(continuum_request, context, common, mosaic=True))
                criteria.extend(continuum)
                branch = aggregate_continuum(context, (setup, *common, *continuum), queue_method=True, mosaic=True)
                branches.append(replace(branch, method_version="queue_custom_continuum_1", decision_refs=(DECISION,),
                    scope="ONE_CUSTOM_GROUP_SAME_ARRAY_PER_POINTING_RMS"))
            if "LINE" in request.intents:
                branch, pairs, pairing = _line_branch(request, context, common, proposed, submitted_scope=prepared is not None)
                branches.append(branch)
            variants.append(dict(diameter_m=position["diameter_m"], criteria=criteria,
                                 branches=branches, line_pairs=pairs, line_pairing=pairing))
        diameters = candidate["position"]["array_inference"]["diameters_m"]
        branches = aggregate_custom_arrays(context.context_id, diameters, variants)
        if not variants:
            branches = tuple(BranchAssessment(intent, context.context_id, "INDETERMINATE", Truth.UNKNOWN,
                REQUIRED[intent], ("ARRAY_INFERENCE_UNRESOLVED",), method_version="queue_custom_array_or_1",
                decision_refs=(DECISION,), scope="SAME_CUSTOM_CANDIDATE_ONLY") for intent in request.intents)
        candidate["science"] = dict(context_id=context.context_id,
            representative_source_row_id=first.reference.raw_row_id,
            metadata_binding="ALL_GROUP_ROWS_EQUAL_SPECTRA_AND_PERFORMANCE",
            array_metadata_basis="REUSED_QUEUE_ROW_HYPOTHESES_NOT_INDEPENDENT_ARRAY_MEASUREMENTS",
            branches=[asdict(b) for b in branches],
            matching_arrays_by_intent={intent: [v["diameter_m"] for v in variants
                if any(b.branch == intent and b.truth is Truth.TRUE for b in v["branches"])] for intent in request.intents},
            reasons=[] if variants else ["ARRAY_INFERENCE_UNRESOLVED"],
            variants=[dict(diameter_m=v["diameter_m"], criteria=[asdict(c) for c in v["criteria"]],
                branches=[asdict(b) for b in v["branches"]], line_pairs=v["line_pairs"],
                line_pairing=None if v["line_pairing"] is None else dict(
                    builder_version=v["line_pairing"].builder_version,
                    proposed_enumeration_complete=v["line_pairing"].proposed_enumeration_complete,
                    candidate_enumeration_complete=v["line_pairing"].candidate_enumeration_complete,
                    reasons=list(v["line_pairing"].reasons))) for v in variants])
    report.update(schema_version="queue_custom_csv_science_2",
        scientific_status="COMPLETE_BRANCHES_EVALUATED_UNDER_PROVISIONAL_CSV_MODEL",
        duplication_status="PER_CANDIDATE_AND_INTENT_RESULTS_NO_SEARCH_WIDE_ABSENCE_CLAIM",
        scientific_request=json_value(request.raw_input),
        request_criteria=[] if setup is None else [asdict(setup)],
        array_aggregation="COMPLETE_SAME_CANDIDATE_ARRAY_BRANCHES_OR",
        science_method_ref=DECISION)
    report["summary"]["matching_candidates_by_intent"] = {intent: sum(
        bool(c["science"]["matching_arrays_by_intent"][intent]) for c in report["candidates"])
        for intent in request.intents}
    report["object_results"] = custom_object_results(report["candidates"])
    report["summary"]["matching_objects_by_intent"] = {intent: sum(
        obj["truth_by_intent"][intent] == Truth.TRUE for obj in report["object_results"])
        for intent in request.intents}
    return report
