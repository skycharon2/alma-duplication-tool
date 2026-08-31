"""Shared pytest controls for optional external-service tests."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add an explicit opt-in switch for live service tests."""

    live_group = parser.getgroup("live service tests")
    live_group.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests that contact live external services",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip every live test unless the caller explicitly opts in."""

    if config.getoption("--run-live"):
        return

    skip_live = pytest.mark.skip(
        reason=(
            "live external-service test; rerun with "
            "--run-live to opt in"
        )
    )

    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip_live)
