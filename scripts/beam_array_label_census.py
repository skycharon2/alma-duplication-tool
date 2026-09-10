"""Archive-wide census: how often does the formula beam strategy's exact
`12-m` / `7-m` antenna_arrays label resolve on real rows?

This is a standalone research/evidence-gathering script, run manually and
opted into deliberately -- it is NOT part of the pytest suite and is not
gated by the "live" marker/--run-live switch (it runs a heavier, unbounded
GROUP BY query, not a small cone search).

Why this exists: docs/primary_beam_search.md documents that the Archive-side
diameter lookup for the FORMULA_PRIMARY_BEAM candidate-selection strategy
(src/alma_duplicate/primary_beam.py) only resolves an antenna_arrays value
that is EXACTLY the string `12-m` or `7-m`, on an explicitly non-mosaic row.
Every other value (a detailed pad:antenna listing, a mixed/heterogeneous
array description, a mosaic row, a missing value) yields
ARRAY_DIAMETER_UNRESOLVED or MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED, and the
row's spatial selection stays NOT_EVALUATED. How large a share of the real
Archive population that affects has never been measured -- see
claude/next_rule_engineering_tasks_2026-09-10.md ("阵列类型分类目前完全没做")
and claude/dev_status_review_2026-09-10.md ("当前精确标签 `12-m`／`7-m` 能覆盖
多少实际样本，需要测量").

This script measures it directly against the live TAP service (bypassing the
production ArchiveClient, which is deliberately scoped to bounded
position/cone queries only -- see docs/archive_client_contract.md -- not
unbounded archive-wide GROUP BY research queries). It follows the same
methodology already used for prior archive-wide census evidence (Notebooks
04b/04c; see docs/evidence/exploration_snapshots.md), and writes its result
in that document's format to docs/evidence/.

This produces MEASUREMENT evidence, not an approved method, not a formal
POS-SINGLE rule, and not a duplication verdict. It does not decide whether
the exact-label heuristic is acceptable; a human still needs to read the
result and decide, per the "application-derived" evidence label the project
already uses for antenna_arrays classification (docs/archive_data_dictionary.md
line 159, "Prefix-based array type is heuristic evidence, not authoritative
classification").

Usage:
    python scripts/beam_array_label_census.py
    python scripts/beam_array_label_census.py --endpoint https://almascience.eso.org/tap
    python scripts/beam_array_label_census.py --no-write   # print only, skip the doc
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_ALMA_TAP_ENDPOINT = "https://almascience.eso.org/tap"
EXACT_LABELS = {"12-m", "7-m"}


def _classify(label: str | None) -> str:
    if label is None:
        return "NULL"
    text = str(label).strip()
    if not text:
        return "BLANK"
    if text in EXACT_LABELS:
        return f"EXACT_{text.upper().replace('-', '')}"
    return "OTHER_DETAILED_OR_MIXED"


def run_census(endpoint: str):
    """Execute the archive-wide GROUP BY query and return its raw rows.

    Imports pyvo lazily so this module can be imported (e.g. for unit-testing
    `_classify` and `_summarize`) without the live dependency installed.
    """
    from pyvo.dal import TAPService

    query = (
        "SELECT antenna_arrays, is_mosaic, COUNT(*) AS n "
        "FROM ivoa.obscore "
        "WHERE science_observation = 'T' "
        "GROUP BY antenna_arrays, is_mosaic "
        "ORDER BY n DESC"
    )
    service = TAPService(endpoint.strip().rstrip("/"))
    result = service.run_sync(query, maxrec=100_000)
    table = result.to_table()
    return query, [
        {
            "antenna_arrays": row["antenna_arrays"],
            "is_mosaic": row["is_mosaic"],
            "n": int(row["n"]),
        }
        for row in table
    ], len(table) >= 100_000  # crude overflow signal; report, do not hide it


def summarize(rows: list[dict]):
    total = sum(r["n"] for r in rows)
    by_class = Counter()
    by_class_nonmosaic = Counter()
    label_samples: dict[str, set[str]] = {}
    for r in rows:
        cls = _classify(r["antenna_arrays"])
        by_class[cls] += r["n"]
        label_samples.setdefault(cls, set()).add(str(r["antenna_arrays"]))
        is_mosaic = str(r["is_mosaic"]).strip().upper()
        if is_mosaic == "F":
            by_class_nonmosaic[cls] += r["n"]
    return total, by_class, by_class_nonmosaic, label_samples


def render_report(endpoint: str, query: str, rows: list[dict], overflow: bool) -> str:
    total, by_class, by_class_nonmosaic, label_samples = summarize(rows)
    captured_at = datetime.now(UTC).isoformat()
    lines = [
        "# Primary-beam array-label applicability census",
        "",
        f"Captured at {captured_at} against `{endpoint}`. This is a live "
        "TAP measurement, not a fixture and not a pinned regression -- the "
        "Archive population changes over time (see "
        "docs/evidence/exploration_snapshots.md for the same caveat on "
        "prior census evidence). Rerun before relying on this for a new "
        "decision if it is more than a few weeks old.",
        "",
        "## Query",
        "",
        "```sql",
        query,
        "```",
        "",
        f"Distinct (`antenna_arrays`, `is_mosaic`) groups returned: {len(rows)}"
        + (" (result may have hit the query row cap; this is a lower bound, not a complete census)" if overflow else ""),
        f"Total `science_observation = 'T'` rows covered: {total}",
        "",
        "## Coverage of the exact-label heuristic",
        "",
        "`primary_beam.py` only resolves a diameter for `antenna_arrays` "
        "exactly equal to `12-m` or `7-m` on an explicitly non-mosaic row "
        "(`is_mosaic = 'F'`). Rows below are classified by that same rule.",
        "",
        "| Classification | All rows | Share of all | Non-mosaic rows | Share of non-mosaic |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    nonmosaic_total = sum(by_class_nonmosaic.values())
    for cls in sorted(by_class, key=lambda c: -by_class[c]):
        all_n = by_class[cls]
        nm_n = by_class_nonmosaic.get(cls, 0)
        all_pct = 100 * all_n / total if total else 0.0
        nm_pct = 100 * nm_n / nonmosaic_total if nonmosaic_total else 0.0
        lines.append(f"| {cls} | {all_n} | {all_pct:.2f}% | {nm_n} | {nm_pct:.2f}% |")
    lines += [
        "",
        "## Sample raw `antenna_arrays` values per classification",
        "",
        "Up to 8 distinct raw values per bucket, for spot-checking that the "
        "classification above is not misreading real labels.",
        "",
    ]
    for cls, samples in sorted(label_samples.items()):
        shown = sorted(samples)[:8]
        more = "" if len(samples) <= 8 else f" (+{len(samples) - 8} more distinct values)"
        lines.append(f"- **{cls}**: {', '.join(repr(s) for s in shown)}{more}")
    lines += [
        "",
        "## Reading this evidence",
        "",
        "This measures how much of the current Archive population the "
        "existing exact-label heuristic can resolve; it does not itself "
        "approve or reject that heuristic as a formal POS-SINGLE method, "
        "and it says nothing about the Queue side (Queue requires an "
        "explicit `PositionInterpretation.antenna_diameter_m`, supplied per "
        "context by the caller, not derived from a label -- see "
        "docs/primary_beam_search.md). A low OTHER_DETAILED_OR_MIXED share "
        "supports the current heuristic as a practical default; a high "
        "share is evidence for prioritizing a real `classify_array_type` "
        "parser (see claude/next_rule_engineering_tasks_2026-09-10.md) "
        "before relying on this strategy at scale.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ALMA_TAP_ENDPOINT)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parents[1]
        / "docs/evidence"
        / f"primary_beam_array_label_census_{datetime.now(UTC).date()}.md",
    )
    parser.add_argument("--no-write", action="store_true", help="print only, do not write the doc")
    args = parser.parse_args()

    query, rows, overflow = run_census(args.endpoint)
    report = render_report(args.endpoint, query, rows, overflow)
    print(report)

    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
