"""Explicit, lazy browser wiring for live Archive TAP access."""

from pathlib import Path

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.clients.archive_replay import (
    RecordedArchiveClient as ReplayClient,
)
from alma_duplicate.ui import create_app
from alma_duplicate.ui import runs as execution


ROOT = Path(__file__).parents[2]
ROW = "w123456abcdef"
ARCHIVE_REPLAY = (
    ROOT / "examples/confirmed_line/archive/manifest.json"
)


def line_form(action="assess"):
    return MultiDict({
        "rows": ROW,
        "setup_id": "setup-1",
        "setup_complete": "on",
        "target_name": "Offline LINE check",
        "ra": "201.365",
        "dec": "-43.019",
        "radius": "30",
        "sources": "ARCHIVE",
        "intents": "LINE",
        "angular": "0.3",
        "redshift": "0.024",
        ROW + "_id": "line-0",
        ROW + "_center": "230.538",
        ROW + "_center_kind": "REST",
        ROW + "_mode": "FDM",
        ROW + "_resolution": "20",
        ROW + "_rms": "0.3",
        "result_limit": "1",
        "action": action,
    })


def live_config(**overrides):
    return {
        "TESTING": True,
        "REPORT_DIRECTORY": None,
        "OFFLINE_ARCHIVE_REPLAY": None,
        "OFFLINE_QUEUE_CSV": None,
        "ARCHIVE_ARRAY_EVIDENCE": None,
        "LIVE_ARCHIVE": True,
    } | overrides


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch):
    import requests

    monkeypatch.setattr(
        requests.sessions.Session,
        "request",
        lambda *a, **k: pytest.fail(
            "live-source UI tests must not access the network"
        ),
    )


def test_live_and_replay_archive_configuration_is_rejected():
    with pytest.raises(ValueError, match="mutually exclusive"):
        create_app(
            live_config(
                OFFLINE_ARCHIVE_REPLAY=ARCHIVE_REPLAY,
            )
        )


def test_live_archive_is_lazy_until_selected_search_ready_assess(
    monkeypatch,
):
    from alma_duplicate.clients import archive_client

    constructed = []

    class UnavailableLiveClient:
        def __init__(self, endpoint):
            constructed.append(endpoint)
            raise OSError(
                "synthetic live construction failure"
            )

    monkeypatch.setattr(
        archive_client,
        "ArchiveClient",
        UnavailableLiveClient,
    )

    monkeypatch.setattr(
        execution,
        "RecordedArchiveClient",
        lambda *a, **k: pytest.fail(
            "live mode fell back to replay"
        ),
    )

    client = create_app(live_config()).test_client()

    html = client.get("/proposed").get_data(as_text=True)

    assert "Archive TAP: live" in html
    assert (
        "A live TAP run does not perform a live AQ lookup"
        in html
    )
    assert constructed == []

    data = line_form("validate")
    assert client.post(
        "/proposed",
        data=data,
    ).status_code == 200
    assert constructed == []

    data["action"] = "download"
    assert client.post(
        "/proposed",
        data=data,
    ).status_code == 200
    assert constructed == []

    invalid = line_form()
    invalid["ra"] = "invalid"
    assert client.post(
        "/proposed",
        data=invalid,
    ).status_code == 200
    assert constructed == []

    solar = line_form()
    solar["target_kind"] = "SUN"
    assert client.post(
        "/proposed",
        data=solar,
    ).status_code == 200
    assert constructed == []

    queue_only = line_form()
    queue_only.setlist(
        "sources",
        ["QUEUE"],
    )

    assert client.post(
        "/proposed",
        data=queue_only,
    ).status_code == 303
    assert constructed == []

    response = client.post(
        "/proposed",
        data=line_form(),
    )

    assert response.status_code == 200
    assert constructed == [
        "https://almascience.eso.org/tap"
    ]
    assert b"No report was created" in response.data


def test_live_archive_uses_shared_entry_without_replay_or_live_aq(
    monkeypatch,
):
    import alma_duplicate.archive_array_evidence as array_evidence
    from alma_duplicate.clients import archive_client

    endpoints = []

    class RecordedTransportLiveClient:
        """Use recorded TAP bytes while exercising the LIVE provider path."""

        def __init__(self, endpoint):
            endpoints.append(endpoint)
            self._client = ReplayClient(
                ARCHIVE_REPLAY
            )

        def search(self, *args, **kwargs):
            return self._client.search(
                *args,
                **kwargs,
            )

    monkeypatch.setattr(
        archive_client,
        "ArchiveClient",
        RecordedTransportLiveClient,
    )

    monkeypatch.setattr(
        execution,
        "RecordedArchiveClient",
        lambda *a, **k: pytest.fail(
            "live mode fell back to replay provider"
        ),
    )

    monkeypatch.setattr(
        array_evidence,
        "load_archive_array_catalog",
        lambda *a, **k: pytest.fail(
            "live TAP implied an AQ lookup"
        ),
    )

    client = create_app(
        live_config()
    ).test_client()

    response = client.post(
        "/proposed",
        data=line_form(),
    )

    assert response.status_code == 303

    assert endpoints == [
        "https://almascience.eso.org/tap"
    ]

    document = client.get(
        response.location + "/download/report"
    ).get_json()

    assert (
        document["sources"]["ARCHIVE"]["status"]
        == "COMPLETED"
    )

    assert (
        document["sources"]["QUEUE"]["status"]
        == "NOT_SELECTED"
    )

    assert (
        "array_evidence"
        not in document["sources"]["ARCHIVE"]
    )

    html = client.get(
        response.location
    ).get_data(as_text=True)

    assert "Assessment run" in html
    assert "Execution status: COMPLETED" in html


@pytest.mark.parametrize(
    "value,live",
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("NO", False),
        ("off", False),
        ("", False),
    ],
)
def test_live_archive_environment_flag_is_explicit(
    monkeypatch,
    value,
    live,
):
    monkeypatch.setenv(
        "ALMA_UI_LIVE_ARCHIVE",
        value,
    )
    monkeypatch.delenv(
        "ALMA_UI_ARCHIVE_REPLAY",
        raising=False,
    )
    monkeypatch.delenv(
        "ALMA_UI_QUEUE_CSV",
        raising=False,
    )

    client = create_app({
        "TESTING": True,
        "REPORT_DIRECTORY": None,
    }).test_client()

    html = client.get(
        "/proposed"
    ).get_data(as_text=True)

    if live:
        assert "Archive TAP: live" in html
        assert 'value="assess"' in html
    else:
        assert "No assessment source is configured" in html
        assert 'value="assess"' not in html


def test_invalid_live_archive_environment_flag_fails_configuration(
    monkeypatch,
):
    monkeypatch.setenv(
        "ALMA_UI_LIVE_ARCHIVE",
        "sometimes",
    )

    with pytest.raises(
        ValueError,
        match="ALMA_UI_LIVE_ARCHIVE must be a boolean flag",
    ):
        create_app({
            "TESTING": True,
            "REPORT_DIRECTORY": None,
        })
