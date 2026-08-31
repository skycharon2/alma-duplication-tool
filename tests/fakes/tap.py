"""Scripted TAP executor used by offline tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from alma_duplicate.clients.archive_contract import (
    TapExecutionError,
    TapResponse,
)


@dataclass(frozen=True, slots=True)
class TapCall:
    adql: str
    maxrec: int


TapAction = TapResponse | TapExecutionError


class FakeTapExecutor:
    """Return scripted TAP responses without network access."""

    def __init__(
        self,
        actions: Iterable[TapAction],
    ) -> None:
        self._actions = list(actions)
        self.calls: list[TapCall] = []

    def execute(
        self,
        adql: str,
        *,
        maxrec: int,
    ) -> TapResponse:
        self.calls.append(
            TapCall(adql=adql, maxrec=maxrec)
        )

        if not self._actions:
            raise AssertionError(
                "FakeTapExecutor has no scripted action left"
            )

        action = self._actions.pop(0)
        if isinstance(action, TapExecutionError):
            raise action

        return action

    @property
    def remaining_action_count(self) -> int:
        return len(self._actions)
