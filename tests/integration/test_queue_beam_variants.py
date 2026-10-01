"""Full coherent MIX branches, one source identity and faithful exported evidence."""

from dataclasses import replace
import json

import pytest

from alma_duplicate.reporting import report_document, report_json_text
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.rules.aggregation import Truth, aggregate_continuum
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.model import CriterionOutcome
from alma_duplicate.rules.queue_beam import aggregate_beam_variants, matching_diameters
from tests.integration.test_queue_continuum import case


def mixed(*, offset=16, count=1, intents=("CONTINUUM",), **changes):
    return case(
        {
            "Use 7-m?": "True",
            "Use TP?": "True",
            "Dec": str(-43.019 + offset / 3600),
            **changes,
        },
        count=count,
        intents=intents,
    )


def test_real_position_seven_matches_twelve_does_not_and_source_is_unique():
    search, report, c = mixed()
    assert search.total_retained == len(report.context_evaluations) == 1
    assert c.criteria == () and c.line_pairs == ()
    assert [v.diameter_m for v in c.beam_variants] == [7, 12]
    assert [v.evaluation.branches[0].status for v in c.beam_variants] == [
        "CRITERIA_MET",
        "CRITERIA_NOT_MET",
    ]
    assert c.branches[0].status == "CRITERIA_MET"
    assert matching_diameters(c.beam_variants) == (7.0,)
    row = c.candidate.context.evidence.row.raw_row
    for v in c.beam_variants:
        assert v.evaluation.candidate is c.candidate
        assert (
            v.variant_id == f"{c.candidate.context.context_id}#beam-{v.diameter_m:g}m"
        )
        for criterion in v.evaluation.criteria:
            assert criterion.context_id == c.candidate.context.context_id
            details = dict(criterion.details)
            assert details["source_row_id"] == row.row_id.value
            assert details["snapshot_sha256"] == row.row_id.snapshot_sha256
    doc = report_document(report)
    assert doc["report_version"] == "4"
    result = doc["context_evaluations"][0]
    assert result["mix_aggregation"]["matching_diameters_m"] == [7.0]
    assert result["mix_aggregation"]["any_variant_met"] is True
    assert json.loads(report_json_text(doc)) == doc
    assert sum(b["count"] for b in inspect_report(doc)["branch_counts"]) == 1


@pytest.mark.parametrize(
    "offset,status", [(0, "CRITERIA_MET"), (25, "CRITERIA_NOT_MET")]
)
def test_both_real_beams(offset, status):
    _, _, c = mixed(offset=offset)
    assert all(v.evaluation.branches[0].status == status for v in c.beam_variants)
    assert c.branches[0].status == status


@pytest.mark.parametrize(
    "truths,status",
    [
        ((Truth.TRUE, Truth.FALSE), "CRITERIA_MET"),
        ((Truth.FALSE, Truth.TRUE), "CRITERIA_MET"),
        ((Truth.FALSE, Truth.FALSE), "CRITERIA_NOT_MET"),
        ((Truth.FALSE, Truth.UNKNOWN), "INDETERMINATE"),
        ((Truth.UNKNOWN, Truth.FALSE), "INDETERMINATE"),
        ((Truth.TRUE, Truth.UNKNOWN), "CRITERIA_MET"),
    ],
)
def test_complete_branch_or_is_symmetric(truths, status):
    # Reverse geometric nesting cannot occur with the same centre/frequency.
    # Inject branch outcomes to test the aggregator independently of geometry.
    _, _, c = mixed()
    variants = tuple(
        replace(
            v,
            evaluation=replace(
                v.evaluation,
                branches=(
                    replace(
                        v.evaluation.branches[0],
                        truth=t,
                        status={
                            Truth.TRUE: "CRITERIA_MET",
                            Truth.FALSE: "CRITERIA_NOT_MET",
                            Truth.UNKNOWN: "INDETERMINATE",
                        }[t],
                    ),
                ),
            ),
        )
        for v, t in zip(c.beam_variants, truths)
    )
    assert aggregate_beam_variants(variants)[0].status == status
    assert matching_diameters(variants) == tuple(
        d for d, t in zip((7.0, 12.0), truths) if t is Truth.TRUE
    )


def test_no_cross_variant_criterion_borrowing():
    _, report, c = mixed()
    variants = []
    # 7-m: good position, bad frequency. 12-m: bad position, good frequency.
    for v in c.beam_variants:
        criteria = tuple(
            replace(r, outcome=CriterionOutcome.NOT_SATISFIED)
            if v.diameter_m == 7 and r.criterion_id == "CONT-FREQ"
            else r
            for r in v.evaluation.criteria
        )
        branch = aggregate_continuum(
            c.candidate.context,
            (*report.request_criteria, *criteria),
            queue_method=True,
        )
        variants.append(
            replace(
                v,
                evaluation=replace(v.evaluation, criteria=criteria, branches=(branch,)),
            )
        )
    assert all(v.evaluation.branches[0].truth is Truth.FALSE for v in variants)
    assert aggregate_beam_variants(variants)[0].status == "CRITERIA_NOT_MET"


def test_hidden_candidates_keep_both_variants_and_line_pair_gap_identity():
    search, _, _ = mixed(count=3, intents=("CONTINUUM", "LINE"))
    report = evaluate_candidate_search(search, queue_continuum=True, queue_line=True)
    assert len(search.candidates) == 1
    doc = report_document(report)
    assert len(doc["context_evaluations"]) == 3
    for c in doc["context_evaluations"]:
        assert len(c["beam_variants"]) == 2
        for v in c["beam_variants"]:
            assert v["line_pairs"]
            for pair in v["line_pairs"]:
                assert (
                    pair["attempt"]["reference"]["candidate_context_id"]
                    == c["context_id"]
                )
                assert all(r["context_id"] == c["context_id"] for r in pair["criteria"])
    gaps = inspect_report(doc)["gap_occurrences"]
    pairs = [g for g in gaps if "pair_identity" in g]
    assert pairs
    assert len({g["pair_identity"]["beam_variant_id"] for g in pairs}) == 6
    for g in pairs:
        node = doc
        for token in g["location"].split("/")[1:]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        assert "criterion_id" in node
    assert len({(g["location"], g["code"], g["side"]) for g in gaps}) == len(gaps)


def test_variant_contract_rejects_cross_context_and_missing_diameter():
    _, _, c = mixed()
    _, _, other = mixed(offset=0)
    with pytest.raises(ValueError, match="identical source"):
        aggregate_beam_variants((c.beam_variants[0], other.beam_variants[1]))
    with pytest.raises(ValueError, match="exactly"):
        aggregate_beam_variants(c.beam_variants[:1])
    with pytest.raises(ValueError, match="diameter"):
        replace(c.beam_variants[0], diameter_m=12.0)
