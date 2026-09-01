"""Production file boundary for current-cycle Queue CSV snapshots."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.parsers.queue_csv import (
    DEFAULT_QUEUE_SOURCE_URL,
    parse_queue_csv_bytes,
)

QUEUE_CSV_CLIENT_VERSION = "1"


class QueueCsvReadError(OSError):
    """Raised when source bytes cannot be read from a local snapshot."""


class QueueCsvClient:
    """Read exact source bytes and delegate source-neutral parsing."""

    def __init__(
        self,
        source_url: str = DEFAULT_QUEUE_SOURCE_URL,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not source_url.strip():
            raise ValueError("source_url must not be blank")
        self._source_url = source_url
        self._clock = clock or (
            lambda: datetime.now(UTC)
        )

    @property
    def source_url(self) -> str:
        return self._source_url

    def parse_bytes(
        self,
        raw_bytes: bytes,
        *,
        captured_at: datetime | None = None,
    ) -> QueueCsvParseResult:
        """Parse bytes already obtained by a caller."""

        return parse_queue_csv_bytes(
            raw_bytes,
            source_url=self._source_url,
            captured_at=captured_at or self._clock(),
        )

    def load(
        self,
        path: str | Path,
        *,
        captured_at: datetime | None = None,
    ) -> QueueCsvParseResult:
        """Read one local snapshot without altering its bytes."""

        source_path = Path(path)
        try:
            raw_bytes = source_path.read_bytes()
        except OSError as exc:
            raise QueueCsvReadError(
                f"could not read Queue CSV snapshot {source_path}"
            ) from exc

        return self.parse_bytes(
            raw_bytes,
            captured_at=captured_at,
        )
