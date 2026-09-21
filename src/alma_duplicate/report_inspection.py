"""Read report v4 without recomputing criteria or inferring a search verdict."""

from collections import Counter

CATEGORIES = (
    "USER_INPUT_MISSING",
    "ARCHIVE_EVIDENCE_MISSING",
    "ASSOCIATION_UNRESOLVED",
    "SCOPE_UNSUPPORTED",
    "SOURCE_OR_SEARCH_INCOMPLETE",
    "METHOD_OR_DEPENDENCY",
    "UNCLASSIFIED",
)
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


def _category(code, side, source):
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


def inspect_report(document):
    """Summarize source gaps and unevaluable evidence, including hidden contexts.

    Counts are evidence occurrences, not failed observations. Shared POS/ANGULAR
    occur once per context, not once per pair. Distinct pair issues stay distinct.
    Unknown codes stay visible as UNCLASSIFIED rather than becoming input advice.
    """
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

    def add(location, code, *, side=None, source=None, context=None, category=None):
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
                "category": category or _category(code, side, source),
            }
        )

    def criterion(r, location, context=None, source=None):
        if r["evaluation"] == "NOT_APPLICABLE":
            return
        if r["approval"] != "APPROVED":
            add(location, "METHOD_UNAPPROVED", source=source, context=context)
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
                )
        else:
            for reason in r["reasons"] or ["UNSPECIFIED_MISSING_EVIDENCE"]:
                add(location, reason, source=source, context=context)

    if kind == "CANDIDATE_EVALUATION":
        for name, source in document["sources"].items():
            if source["status"] not in {"COMPLETED", "NOT_SELECTED"}:
                add(
                    f"sources/{name}",
                    source["status"],
                    source=name,
                    category="SOURCE_OR_SEARCH_INCOMPLETE",
                )
            if source.get("requested_filters_fully_evaluated") is False:
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
        for c in contexts:
            cid, source = c["context_id"], c["reference"]["source"]
            for r in c["criteria"]:
                criterion(r, f"{cid}/criteria/{r['criterion_id']}", cid, source)
            for pair in c["line_pairs"]:
                wid = pair["attempt"]["proposed_window_id"]
                for r in pair["criteria"]:
                    if r["criterion_id"] not in {"POS-SINGLE", "ANGULAR"}:
                        criterion(
                            r,
                            f"{cid}/line_pairs/{wid}/{r['criterion_id']}",
                            cid,
                            source,
                        )
            for b in c["branches"]:
                # Aggregate placeholders are explained by the underlying conditions.
                for reason in b["reasons"]:
                    if reason in ASSOCIATION | SCOPE | USER:
                        add(
                            f"{cid}/branches/{b['branch']}",
                            reason,
                            source=source,
                            context=cid,
                        )
    groups = []
    for name in CATEGORIES:
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
        "inspection_version": "1",
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
