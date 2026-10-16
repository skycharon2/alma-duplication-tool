"""Official Archive mirrors and request-local failover time budgets."""
from contextlib import contextmanager
from contextvars import ContextVar
import math
import time
from urllib.parse import urlsplit

ARCHIVE_ORIGINS = (
    "https://almascience.eso.org",
    "https://almascience.nao.ac.jp",
    "https://almascience.nrao.edu",
)
_budget = ContextVar("archive_request_budget", default=None)


def validate_origins(origins):
    origins = tuple(origins)
    if not origins or len(set(origins)) != len(origins) or any(o not in ARCHIVE_ORIGINS for o in origins):
        raise ValueError("Select unique official Archive origins")
    return origins


def aq_search_endpoint(value, *, origin=None):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("Invalid endpoint")
    parsed = urlsplit(value)
    allowed = (origin,) if origin is not None else ARCHIVE_ORIGINS
    if (parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment
            or f"https://{parsed.hostname}" not in allowed
            or parsed.path not in ("/aq/service/api/search", "/aq/service/api/search/")):
        raise ValueError("Invalid endpoint")
    return f"https://{parsed.hostname}/aq/service/api/search/observations/_search"


class ArchiveBudgetExpired(TimeoutError):
    pass


@contextmanager
def request_budget(seconds, clock=time.monotonic):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Archive time budget must be finite and positive")
    token = _budget.set((clock() + seconds, clock))
    try:
        yield
    finally:
        _budget.reset(token)


def request_timeout(default=(10, 60)):
    """Do not start requests after budget expiry; cap connect/idle timeouts.

    This bounds scheduling and idle waits, not a hard deadline on a streaming
    response whose server continuously sends data. Never abandon background I/O.
    """
    budget = _budget.get()
    if budget is None:
        return default
    deadline, clock = budget
    remaining = deadline - clock()
    if remaining <= 0:
        raise ArchiveBudgetExpired("Archive acquisition time budget exhausted")
    return tuple(min(value, remaining / 2) for value in default)
