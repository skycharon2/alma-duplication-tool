"""Read report v4 without recomputing criteria or inferring a search verdict."""

from collections import Counter

CATEGORIES_V1 = (
    "USER_INPUT_MISSING",
    "ARCHIVE_EVIDENCE_MISSING",
    "ASSOCIATION_UNRESOLVED",
    "SCOPE_UNSUPPORTED",
    "SOURCE_OR_SEARCH_INCOMPLETE",
    "METHOD_OR_DEPENDENCY",
    "UNCLASSIFIED",
)
CATEGORIES_V2 = (
    "USER_INPUT_MISSING",
    "ARCHIVE_EVIDENCE_MISSING",
    "QUEUE_EVIDENCE_MISSING",
    "ASSOCIATION_UNRESOLVED",
    "SCOPE_UNSUPPORTED",
    "SOURCE_OR_SEARCH_INCOMPLETE",
    "METHOD_OR_DEPENDENCY",
    "UNCLASSIFIED",
)
CATEGORIES = CATEGORIES_V2
ASSOCIATION = {
    "SOURCE_SPW_COMPONENT_UNASSIGNED",
    "PAIR_REFERENCE_UNRESOLVED",
    "PAIR_REFERENCE_REQUIRED",
    "CANDIDATE_ASSOCIATION_UNLINKED",
    "CONFLICTING_CONTEXT_ALTERNATIVES",
}
SCOPE = {
    "BRANCH_SCOPE_UNSUPPORTED",
    "ARCHIVE_SOURCE_REQUIRED",
    "ARCHIVE_LINE_MAPPING_REQUIRED",
    "SINGLE_FIELD_CANDIDATE_REQUIRED",
    "FIXED_SINGLE_POINT_REQUEST_REQUIRED",
    "UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED",
    "CONFLICTING_POSITION_INTERPRETATION",
    "ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED",
}
USER = {
    "SOURCE_REDSHIFT_REQUIRED",
    "UNIQUE_WINDOW_LINE_SENSITIVITY_REQUIRED",
    "CONFLICTING_PLANNED_RESOLUTIONS",
    "NO_PROPOSED_LINE_WINDOWS",
    "PROPOSED_ENUMERATION_INCOMPLETE",
    "UNIQUE_AGGREGATE_RMS_REQUIRED",
}
CANDIDATE = {
    "MISSING_COUNT",
    "MASKED_COUNT",
    "INVALID_COUNT",
    "CANDIDATE_MODE_EVIDENCE_REQUIRED",
}


def _category_v1(code, side, source):
    if code in ASSOCIATION:
        return "ASSOCIATION_UNRESOLVED"
    if code in SCOPE:
        return "SCOPE_UNSUPPORTED"
    if code in USER or side == "PROPOSED" or code.startswith(("PROPOSED_", "PLANNED_")):
        return "USER_INPUT_MISSING"
    if code == "ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED" or code == "METHOD_UNAPPROVED":
        return "METHOD_OR_DEPENDENCY"
    if source == "ARCHIVE" and (
        side == "CANDIDATE"
        or code in CANDIDATE
        or code.startswith(
            ("CANDIDATE_", "COMPONENT_", "EXACT_COMPONENT_", "UNIQUE_COMPONENT_")
        )
    ):
        return "ARCHIVE_EVIDENCE_MISSING"
    return "UNCLASSIFIED"


V2_SCOPE = {
    "POSITION_SCOPE_UNRESOLVED",
    "QUEUE_POSITION_SCOPE_UNRESOLVED",
}
V2_METHOD = {
    "QUEUE_RESOLUTION_COARSER_THAN_PLANNED",
}


def _category(code, side, source, inspection_version):
    legacy = _category_v1(code, side, source)
    if inspection_version == "1":
        return legacy
    if code in V2_SCOPE:
        return "SCOPE_UNSUPPORTED"
    if code in V2_METHOD:
        return "METHOD_OR_DEPENDENCY"
    if legacy != "UNCLASSIFIED":
        return legacy
    if source == "QUEUE" and (
        side == "CANDIDATE"
        or code in CANDIDATE
        or code.startswith(
            ("CANDIDATE_", "COMPONENT_", "EXACT_COMPONENT_", "UNIQUE_COMPONENT_")
        )
    ):
        return "QUEUE_EVIDENCE_MISSING"
    return legacy


def inspect_report(document, *, inspection_version="3"):
    """Summarize source gaps and unevaluable evidence, including hidden contexts.

    Counts are evidence occurrences, not failed observations. Shared POS/ANGULAR
    occur once per context, not once per pair. Distinct pair issues stay distinct.
    Unknown codes stay visible as UNCLASSIFIED rather than becoming input advice.
    """
    if inspection_version not in {"1", "2", "3"}:
        raise ValueError("Inspection version must be 1, 2 or 3")
    if document.get("report_version") != "4":
        raise ValueError("Inspection requires report version 4")
    kind = document.get("report_kind")
    if kind not in {"CANDIDATE_EVALUATION", "SOLAR_EXEMPTION"}:
        raise ValueError("Unknown report kind")
    contexts = document["context_evaluations"]
    if len({c["context_id"] for c in contexts}) != len(contexts):
        raise ValueError("Duplicate report context identity")
    occurrences = []
    seen = set()

    def add(location, code, *, side=None, source=None, context=None, category=None, pair_identity=None):
        key = (location, code, side)
        if key in seen:
            return
        seen.add(key)
        occurrences.append(
            {
                "location": location,
                "code": code,
                "side": side,
                "source": source,
                "context_id": context,
                **({"pair_identity": pair_identity} if pair_identity is not None else {}),
                "category": category
                or _category(code, side, source, inspection_version),
            }
        )

    def criterion(r, location, context=None, source=None, pair_identity=None):
        if r["evaluation"] == "NOT_APPLICABLE":
            return
        if r["approval"] != "APPROVED":
            add(location, "METHOD_UNAPPROVED", source=source, context=context, pair_identity=pair_identity)
        if r["outcome"] is not None:
            return
        if r["issues"]:
            for issue in r["issues"]:
                add(
                    location,
                    issue["code"],
                    side=issue["side"],
                    source=source,
                    context=context,
                    pair_identity=pair_identity,
                )
        else:
            for reason in r["reasons"] or ["UNSPECIFIED_MISSING_EVIDENCE"]:
                add(location, reason, source=source, context=context, pair_identity=pair_identity)

    if kind == "CANDIDATE_EVALUATION":
        for name, source in document["sources"].items():
            if inspection_version == "3" and name == "ARCHIVE":
                acquisition = source.get("array_evidence", {}).get("acquisition", {})
                if acquisition.get("status") in {"FAILED", "INCOMPLETE"}:
                    add(
                        "sources/ARCHIVE/array_evidence/acquisition",
                        "ARCHIVE_AQ_" + acquisition["status"],
                        source=name,
                        category="SOURCE_OR_SEARCH_INCOMPLETE",
                    )
            if source["status"] not in {"COMPLETED", "NOT_SELECTED"}:
                add(
                    f"sources/{name}",
                    source["status"],
                    source=name,
                    category="SOURCE_OR_SEARCH_INCOMPLETE",
                )
            filters_incomplete = (
                source.get(
                    "requested_filters_fully_evaluated"
                )
                is False
            )
            if (
                filters_incomplete
                and (
                    inspection_version == "1"
                    or source["status"] == "COMPLETED"
                )
            ):
                add(
                    f"sources/{name}/filters",
                    "REQUESTED_FILTERS_NOT_FULLY_EVALUATED",
                    source=name,
                    category="SOURCE_OR_SEARCH_INCOMPLETE",
                )
        for i, issue in enumerate(document["request"]["issues"]):
            if issue["category"] == "MISSING":
                add(f"request/issues/{i}", issue["code"], side=issue.get("side"))
        for r in document["request_criteria"]:
            criterion(r, f"request_criteria/{r['criterion_id']}")
        for context_index, c in enumerate(contexts):
            cid, source = c["context_id"], c["reference"]["source"]
            variants = c.get("beam_variants", [])
            if variants and (
                [v.get("diameter_m") for v in variants] != [7, 12]
                or any(v.get("context_id") != cid or v.get("variant_id") != f"{cid}#beam-{v['diameter_m']:g}m"
                       for v in variants)
                or source not in {"QUEUE", "ARCHIVE"} or c["criteria"] or c["line_pairs"]
            ):
                raise ValueError("Invalid coherent source beam variants")
            for variant_index, scope in enumerate(variants or [c]):
                scope_id = scope["variant_id"] if variants else cid
                pointer = f"/context_evaluations/{context_index}"
                if variants:
                    pointer += f"/beam_variants/{variant_index}"
                for r in scope["criteria"]:
                    criterion(r, f"{scope_id}/criteria/{r['criterion_id']}", cid, source)
                for pair_index, pair in enumerate(scope["line_pairs"]):
                    attempt = pair["attempt"]
                    if "proposed_window_id" in attempt:
                        wid = attempt["proposed_window_id"]
                    else:
                        reference = attempt.get("reference")
                        if (
                            not isinstance(reference, dict)
                            or "proposed_window_id" not in reference
                        ):
                            raise ValueError(
                                "Line pair lacks proposed window identity"
                            )
                        wid = reference["proposed_window_id"]
                    identity = None
                    if inspection_version == "3":
                        identity = {
                            "context_id": cid,
                            **({"beam_variant_id": scope_id} if variants else {}),
                            "proposed_window_id": wid,
                            "pair_index": pair_index,
                            "reference": attempt.get("reference"),
                        }
                    for criterion_index, r in enumerate(pair["criteria"]):
                        if r["criterion_id"] not in {"POS-SINGLE", "ANGULAR"}:
                            criterion(
                                r,
                                (f"{pointer}/line_pairs/{pair_index}/criteria/{criterion_index}"
                                 if inspection_version == "3"
                                 else f"{scope_id}/line_pairs/{wid}/{r['criterion_id']}"),
                                cid,
                                source,
                                identity,
                            )
                for b in scope["branches"]:
                    # Aggregate placeholders are explained by the underlying conditions.
                    for reason in b["reasons"]:
                        if reason in ASSOCIATION | SCOPE | USER:
                            add(
                                f"{scope_id}/branches/{b['branch']}",
                                reason,
                                source=source,
                                context=cid,
                            )
    groups = []
    categories = CATEGORIES_V1 if inspection_version == "1" else CATEGORIES_V2
    for name in categories:
        values = [o for o in occurrences if o["category"] == name]
        groups.append(
            {
                "category": name,
                "occurrences": len(values),
                "affected_contexts": len(
                    {o["context_id"] for o in values if o["context_id"] is not None}
                ),
                "unscoped_occurrences": sum(o["context_id"] is None for o in values),
                "codes": dict(sorted(Counter(o["code"] for o in values).items())),
            }
        )
    branches = Counter(
        (c["reference"]["source"], b["branch"], b["status"])
        for c in contexts
        for b in c["branches"]
    )
    return {
        "inspection_version": inspection_version,
        "report_version": "4",
        "report_kind": kind,
        "assessment": document["assessment"],
        "search_assessment": document["search_assessment"],
        "scope": document["evaluation_scope"],
        "source_statuses": {s: v["status"] for s, v in document["sources"].items()},
        "branch_counts": [
            {"source": s, "branch": b, "status": status, "count": n}
            for (s, b, status), n in sorted(branches.items())
        ],
        "gap_counting_scope": "ALL_RETAINED_CONTEXTS; occurrences overlap; not duplicate counts",
        "gap_categories": groups,
        "gap_occurrences": occurrences,
        "search_wide_verdict": "NOT_PROVIDED",
    }
