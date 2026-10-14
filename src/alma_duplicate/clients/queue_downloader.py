"""Bounded, HTTPS-only acquisition of the public ALMA Queue CSV.

Network transport is separate from parsing, persistence and active-snapshot selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

OFFICIAL_QUEUE_CSV_URL = (
    "https://almascience.eso.org/documents-and-tools/latest/duplication-check-csv"
)

MAX_CSV_BYTES = 64 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 45
_APPROVED_HOST = "almascience.eso.org"
_ALLOWED_TYPES = {
    "text/csv", "text/plain", "application/csv",
    "application/octet-stream", "application/vnd.ms-excel",
}


class QueueDownloadError(ValueError):
    """The official-source download could not be completed safely."""


@dataclass(frozen=True, slots=True)
class DownloadedQueue:
    raw_bytes: bytes
    final_url: str
    retrieved_at: datetime
    etag: str | None = None
    last_modified: str | None = None


def _check_official_url(url: str) -> None:
    """Limit outgoing requests and redirects to the official download service."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (ValueError, AttributeError) as exc:
        raise QueueDownloadError("invalid official Queue download URL") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname != _APPROVED_HOST
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/documents-and-tools/")
        or parsed.fragment
    ):
        raise QueueDownloadError("Queue downloads must stay on the approved ALMA HTTPS origin")


class _OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_queue_csv(
    *, url: str = OFFICIAL_QUEUE_CSV_URL,
    opener=None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_CSV_BYTES,
    clock=None,
) -> DownloadedQueue:
    """Return exact CSV bytes; never write files, parse, or choose an active version.

    ``opener`` is injectable for offline tests. In production a redirect-checked
    urllib opener is used. HTTP validators are informational in PR1: SHA-256,
    not ETag or Last-Modified, decides whether downloaded contents changed.
    """
    _check_official_url(url)
    if type(timeout) is not int or timeout < 1:
        raise ValueError("timeout must be a positive integer")
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    opener = opener if opener is not None else build_opener(_OfficialRedirects())
    req = Request(
        url,
        headers={"Accept": "text/csv, text/plain, application/octet-stream",
                 "Accept-Encoding": "identity",
                 "User-Agent": "alma-duplication-tool-queue-updater/1"},
    )
    try:
        with opener.open(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise QueueDownloadError(f"unexpected HTTP status {status}")
            final_url = response.geturl()
            _check_official_url(final_url)
            headers = response.headers
            media_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if media_type and media_type not in _ALLOWED_TYPES:
                raise QueueDownloadError("official endpoint did not serve an expected CSV content type")
            if headers.get("Content-Encoding", "identity").lower() != "identity":
                raise QueueDownloadError("compressed response not supported; exact CSV bytes required")
            length = headers.get("Content-Length")
            if length is not None:
                try:
                    announced = int(length)
                except ValueError as exc:
                    raise QueueDownloadError("invalid Content-Length") from exc
                if announced < 0 or announced > max_bytes:
                    raise QueueDownloadError("Queue CSV exceeds configured size limit")
            chunks = bytearray()
            while True:
                block = response.read(min(65536, max_bytes - len(chunks) + 1))
                if not block:
                    break
                chunks.extend(block)
                if len(chunks) > max_bytes:
                    raise QueueDownloadError("Queue CSV exceeds configured size limit")
            if not chunks:
                raise QueueDownloadError("empty Queue CSV download")
            if length is not None and len(chunks) != announced:
                raise QueueDownloadError("incomplete Queue CSV response")
            # A proxy may return an HTML login/error page with HTTP 200.
            opening = bytes(chunks[:512]).lstrip(b"\xef\xbb\xbf\t\r\n ").lower()
            if opening.startswith((b"<!doctype html", b"<html", b"<?xml", b"<head", b"<body")):
                raise QueueDownloadError("download returned a page, not a Queue CSV")
            instant = (clock or (lambda: datetime.now(UTC)))()
            if not isinstance(instant, datetime) or instant.utcoffset() is None:
                raise ValueError("retrieval clock must return timezone-aware datetime")
            return DownloadedQueue(
                bytes(chunks), final_url, instant,
                etag=headers.get("ETag"), last_modified=headers.get("Last-Modified"),
            )
    except HTTPError as exc:
        raise QueueDownloadError(f"official Queue server returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise QueueDownloadError(f"official Queue download failed: {type(exc).__name__}") from exc
