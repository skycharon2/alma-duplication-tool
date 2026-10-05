"""Acquire array evidence after TAP retention, without changing TAP candidates."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from alma_duplicate.archive_array_evidence import (
    ArchiveArrayCatalog, ArchiveArrayCatalogMode, ArchiveArrayCatalogProvenance,
    archive_array_catalog_report_metadata,
)
from alma_duplicate.clients.archive_aq_client import ArchiveAqError, ArchiveAqFetchResult
from alma_duplicate.domain.candidate_search import SourceSearchExecution

ArchiveArrayFetcher = Callable[[tuple[str, ...]], ArchiveAqFetchResult]


@dataclass(frozen=True)
class ArchiveArrayAcquisition:
    catalog: ArchiveArrayCatalog
    metadata: dict

    @property
    def unavailable(self):
        return self.metadata["acquisition"]["status"] in {"FAILED", "INCOMPLETE"}


def _check_result(result, members):
    """Reject provider contract mistakes rather than silently relabeling evidence."""
    if (not isinstance(result, ArchiveAqFetchResult)
            or result.catalog.provenance.mode is not ArchiveArrayCatalogMode.LIVE
            or tuple(q.member_ous_uid for q in result.queries) != members):
        raise ValueError("AQ fetcher must return a LIVE result for exactly the requested Members")
    queries = {q.member_ous_uid: q for q in result.queries}
    counts = dict.fromkeys(members, 0)
    for record in result.catalog.records:
        query = queries.get(record.member_ous_uid)
        if query is None or (record.url, record.retrieved_at, record.response_sha256) != (
                query.url, query.retrieved_at, query.response_sha256):
            raise ValueError("AQ record provenance disagrees with its Member query")
        counts[record.member_ous_uid] += 1
    if any(type(q.total_hits) is not int or q.total_hits != counts[q.member_ous_uid]
           for q in result.queries):
        raise ValueError("AQ query counts disagree with catalog records")


def acquire_archive_arrays(source: SourceSearchExecution,
                           fetcher: ArchiveArrayFetcher) -> ArchiveArrayAcquisition:
    """An enabled but failed/skipped acquisition always supplies an empty catalog.

    None would select legacy TAP-only inference and is never returned here.
    Only expected acquisition errors become structured source evidence failures.
    """
    if source.source != "ARCHIVE":
        raise ValueError("AQ acquisition requires Archive search execution")
    catalog = ArchiveArrayCatalog((), ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE))
    members = tuple(dict.fromkeys(
        row.context.evidence.row_link.association_key.context.member_ous_uid
        for row in source.retained_rows if row.context.evidence.row_link.is_linked
    )) if source.status == "COMPLETED" else ()
    data = {"status": "SKIPPED", "reason": None, "requested_members": list(members),
            "queries": [], "error": None, "started_at": None, "finished_at": None}
    if source.status != "COMPLETED":
        data["reason"] = "TAP_NOT_COMPLETED"
    elif not source.retained_rows:
        data["reason"] = "NO_RETAINED_ARCHIVE_CONTEXTS"
    elif not members:
        data["reason"] = "NO_LINKED_ARCHIVE_MEMBERS"
    else:
        data["started_at"] = datetime.now(timezone.utc).isoformat()
        try:
            result = fetcher(members)
        except ArchiveAqError as exc:
            data["status"] = "INCOMPLETE" if exc.code == "INCOMPLETE" else "FAILED"
            data["error"] = {"code": exc.code, "member_ous_uid": exc.member_ous_uid}
        else:
            _check_result(result, members)
            catalog = result.catalog
            data["status"] = "COMPLETED"
            data["queries"] = [asdict(q) for q in result.queries]
            data["properties_url"] = result.properties_url
        data["finished_at"] = datetime.now(timezone.utc).isoformat()
    metadata = archive_array_catalog_report_metadata(catalog)
    metadata["acquisition"] = data
    return ArchiveArrayAcquisition(catalog, metadata)
