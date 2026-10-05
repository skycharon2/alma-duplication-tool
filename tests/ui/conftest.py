"""UI tests configure their own source environment, independent of the shell."""
import os

import pytest


@pytest.fixture(autouse=True)
def isolated_ui_environment(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith("ALMA_UI_"):
            monkeypatch.delenv(name)
