"""Retry whole Archive operations across official mirrors, never combine rows."""
from dataclasses import replace
from datetime import datetime, timezone
import time

from alma_duplicate.clients.archive_contract import ArchiveQueryErrorKind as K
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus as S
from alma_duplicate.clients.archive_aq_client import ArchiveAqError
from alma_duplicate.archive_endpoints import (
    ARCHIVE_ORIGINS, ArchiveBudgetExpired, request_budget, request_timeout, validate_origins,
)

DEFAULT_BUDGET_SECONDS = 180


def _attempt(origin, started, *, status, error=None, **extra):
    return dict(origin=origin, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
                status=str(status), error=None if error is None else str(error), **extra)


def _now():
    return datetime.now(timezone.utc).isoformat()


class MirroredArchiveClient:
    """One fresh TAP client per attempt; successful empty results end the search."""

    def __init__(self, *, origins=ARCHIVE_ORIGINS, budget_seconds=DEFAULT_BUDGET_SECONDS,
                 completeness_policy="COUNT_FIRST", client_factory=None, clock=time.monotonic):
        self.origins = validate_origins(origins)
        self.budget_seconds = budget_seconds
        self.completeness_policy = completeness_policy
        self.client_factory = client_factory
        self.clock = clock

    def search(self, spec):
        from alma_duplicate.clients.archive_client import ArchiveClient
        factory = self.client_factory or ArchiveClient
        attempts, last = [], None
        with request_budget(self.budget_seconds, self.clock):
            for origin in self.origins:
                started = _now()
                try:
                    request_timeout()
                    result = factory(origin + "/tap", completeness_policy=self.completeness_policy).search(spec)
                except ArchiveBudgetExpired:
                    attempts.append(_attempt(origin, started, status="NOT_COMPLETED", error="TIME_BUDGET_EXHAUSTED"))
                    break
                attempts.append(_attempt(origin, started, status=result.status, error=result.error_kind,
                                         query_run_id=result.provenance.query_run_id,
                                         query_hash=result.provenance.query_hash))
                last = result
                # Syntax/contract failures must not be masked by changing sites.
                retry = (result.status in {S.OVERFLOW, S.COUNT_MISMATCH}
                         or result.error_kind in {K.SERVICE_ERROR, K.RESPONSE_FORMAT_ERROR,
                                                  K.UNKNOWN_QUERY_STATUS, K.INVALID_COUNT})
                if result.status is S.COMPLETE or not retry:
                    break
        if last is None:
            raise ArchiveBudgetExpired("Archive TAP time budget exhausted before a result")
        return replace(last, provenance=replace(last.provenance, mirror_attempts=tuple(attempts)))


class MirroredArchiveAqClient:
    """Restart the entire Member batch at each mirror, discarding partial batches."""

    def __init__(self, *, origins=ARCHIVE_ORIGINS, budget_seconds=DEFAULT_BUDGET_SECONDS,
                 client_factory=None, clock=time.monotonic):
        self.origins = validate_origins(origins)
        self.budget_seconds = budget_seconds
        self.client_factory = client_factory
        self.clock = clock

    def fetch_members(self, members):
        from alma_duplicate.clients.archive_aq_client import ArchiveAqClient
        factory = self.client_factory or ArchiveAqClient
        # Materialize once: a generator must survive retrying the whole batch.
        if isinstance(members, (str, bytes)):
            raise ValueError("members must be an iterable of Member UIDs")
        members = tuple(members)
        attempts = []
        with request_budget(self.budget_seconds, self.clock):
            for origin in self.origins:
                started = _now()
                try:
                    request_timeout()
                    result = factory(origin=origin).fetch_members(members)
                except ArchiveBudgetExpired:
                    attempts.append(_attempt(origin, started, status="FAILED", error="TIME_BUDGET_EXHAUSTED"))
                    raise ArchiveAqError("TIME_BUDGET_EXHAUSTED", attempts=tuple(attempts)) from None
                except ArchiveAqError as exc:
                    attempts.append(_attempt(origin, started, status="FAILED", error=exc.code,
                                             http_status=exc.http_status, member_ous_uid=exc.member_ous_uid))
                    retry = (exc.code in {"TRANSPORT_ERROR", "INCOMPLETE", "JSON_INVALID", "RESPONSE_INVALID"}
                             or (exc.code == "HTTP_ERROR" and exc.http_status is not None
                                 and (exc.http_status in {408, 429} or 500 <= exc.http_status <= 599)))
                    if not retry or origin == self.origins[-1]:
                        raise ArchiveAqError(exc.code, exc.member_ous_uid, http_status=exc.http_status,
                                             attempts=tuple(attempts)) from None
                else:
                    attempts.append(_attempt(origin, started, status="COMPLETED"))
                    return replace(result, mirror_attempts=tuple(attempts))
