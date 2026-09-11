"""Observation-level presentation groups for candidate-search rows.

The ALMA Archive Query interface lists one entry per (Member OUS, source):
its observation documents are keyed ``<member_ous_uid>.source.<target_name>``
(verified 2026-09-11; ``2021.A.00028.S`` has four such entries, one of them a
science target). Grouping candidate rows the same way makes a search result
count comparable with the supervisor's CASE1/CASE2 entry counts.

Groups are for presentation only. Every row keeps its own coherent context and
filter record; values are never merged across rows, and a group never becomes
a duplication verdict. Rows whose key is incomplete stay in singleton groups.
"""
from __future__ import annotations

from dataclasses import dataclass

from alma_duplicate.domain.candidate_search import (
    CandidateDisposition as D, CandidateRecord, CandidateSearchResult,
)
from alma_duplicate.domain.comparison import ArchiveContextEvidence, QueueContextEvidence

GROUPING_VERSION = "observation_group_1"


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    source: str
    key: tuple[str, ...]
    key_complete: bool
    science: bool | None
    rows: tuple[CandidateRecord, ...]
    grouping_version: str = GROUPING_VERSION

    @property
    def disposition(self) -> D:
        """Best row outcome: one matched coherent row is enough to show the entry."""
        dispositions = {row.disposition for row in self.rows}
        for candidate in (D.MATCHED_FILTERS, D.RETAINED_UNEVALUATED):
            if candidate in dispositions:
                return candidate
        return D.EXCLUDED

    @property
    def matched_rows(self) -> tuple[CandidateRecord, ...]:
        return tuple(r for r in self.rows if r.disposition is D.MATCHED_FILTERS)

    @property
    def label(self) -> str:
        return " | ".join(self.key)


def _text(value) -> str | None:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _key(row: CandidateRecord) -> tuple[str, tuple[str, ...], bool, bool | None]:
    evidence = row.context.evidence
    if isinstance(evidence, ArchiveContextEvidence):
        raw = evidence.prepared.raw_row
        member, target = _text(raw.get("member_ous_uid")), _text(raw.get("target_name"))
        science = evidence.prepared.normalized_metadata.science_observation.value
        if member and target:
            return "ARCHIVE", (member, target), True, science
        return "ARCHIVE", (row.context.context_id,), False, science
    if isinstance(evidence, QueueContextEvidence):
        key = evidence.row.group_key
        parts = (_text(key.project_code), _text(key.target_name), _text(key.band))
        if all(parts):
            return "QUEUE", parts, True, True
        return "QUEUE", (row.context.context_id,), False, True
    raise TypeError("Unsupported candidate context")


def group_candidates(result: CandidateSearchResult) -> tuple[CandidateGroup, ...]:
    """Group every processed row (excluded rows included) in deterministic order."""
    groups: dict[tuple[str, tuple[str, ...]], list] = {}
    meta: dict[tuple[str, tuple[str, ...]], tuple[bool, bool | None]] = {}
    for source in (result.archive, result.queue):
        for row in source.rows:
            name, key, complete, science = _key(row)
            groups.setdefault((name, key), []).append(row)
            previous = meta.get((name, key))
            # A science flag that differs inside one key is reported as unknown.
            meta[(name, key)] = (complete, science if previous is None or previous[1] == science else None)
    order = {"ARCHIVE": 0, "QUEUE": 1}
    return tuple(
        CandidateGroup(name, key, meta[(name, key)][0], meta[(name, key)][1],
                       tuple(sorted(rows, key=lambda r: r.context.context_id)))
        for (name, key), rows in sorted(groups.items(), key=lambda item: (order[item[0][0]], item[0][1]))
    )


def visible_groups(groups: tuple[CandidateGroup, ...], *, science_only: bool = False) -> tuple[CandidateGroup, ...]:
    """Groups with at least one non-excluded row; optionally science targets only."""
    return tuple(
        g for g in groups
        if g.disposition is not D.EXCLUDED and (not science_only or g.science is True)
    )
