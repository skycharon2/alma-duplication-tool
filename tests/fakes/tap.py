"""Scripted TAP executor used by offline tests."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from alma_duplicate.clients.archive_contract import (
    TapExecutionError,
    TapResponse,
    TapFieldMetadata,
)
from alma_duplicate.clients.archive_queries import ARCHIVE_OPTIONAL_COLUMNS


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
        *,
        projection_action: TapAction | None = None,
    ) -> None:
        self._actions = list(actions)
        self.calls: list[TapCall] = []
        self.projection_calls: list[TapCall] = []
        self.projection_action = projection_action

    def execute(
        self,
        adql: str,
        *,
        maxrec: int,
    ) -> TapResponse:
        # Dedicated schema route keeps existing COUNT/arithmetic scripts explicit.
        # Every projection call is recorded separately, not discarded.
        if adql.startswith("SELECT column_name\nFROM TAP_SCHEMA.columns"):
            self.projection_calls.append(TapCall(adql=adql, maxrec=maxrec))
            action = self.projection_action
            if action is None:
                action = TapResponse(
                    rows=tuple({"column_name": name} for name in ARCHIVE_OPTIONAL_COLUMNS
                               if f"'{name}'" in adql),
                    declared_columns=("column_name",),
                    field_metadata=(TapFieldMetadata(
                        name="column_name", datatype="char", arraysize="*",
                        unit=None, ucd=None, utype=None, xtype=None, description=None,
                    ),), query_status_raw="OK",
                )
            if isinstance(action, TapExecutionError):
                raise action
            return action
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
