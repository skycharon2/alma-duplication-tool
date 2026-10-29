"""PR 3A: behavior-preserving browser workflow policy extraction.

These tests must not access Archive, Queue, or the network.
"""

import pytest
from werkzeug.datastructures import MultiDict

from alma_duplicate.ui import create_app
from alma_duplicate.ui.workflow_policy import (
    apply_browser_source_policy, is_fixed_mosaic, should_enable_mosaic_v2_on_scope_change,
)
from tests.ui.test_default_single_pointing_contract import continuum_form


@pytest.mark.parametrize("kind,geometry,mosaic", [
    ("FIXED", "MOSAIC", True),
    ("FIXED", "SINGLE_POINTING", False),
    ("MOVING", "MOSAIC", False),
    ("SUN", "MOSAIC", False),
    ("FIXED", "UNKNOWN", False),
])
def test_workflow_identity_preserves_original_scope(kind, geometry, mosaic):
    assert is_fixed_mosaic({"target_kind": kind, "geometry": geometry}) is mosaic


@pytest.mark.parametrize("kind,geometry,expected", [
    ("FIXED", "MOSAIC", ["ARCHIVE"]),
    ("FIXED", "SINGLE_POINTING", ["ARCHIVE", "QUEUE"]),
    ("MOVING", "MOSAIC", ["ARCHIVE", "QUEUE"]),
])
def test_browser_source_policy_only_constrains_fixed_mosaic(kind, geometry, expected):
    values = {"target_kind": kind, "geometry": geometry,
              "sources": ["ARCHIVE", "QUEUE"]}
    apply_browser_source_policy(values)
    assert values["sources"] == expected


def test_source_policy_does_not_add_sources_to_single_pointing():
    values = {"target_kind": "FIXED", "geometry": "SINGLE_POINTING",
              "sources": ["QUEUE"]}
    apply_browser_source_policy(values)
    assert values["sources"] == ["QUEUE"]


def test_blank_mosaic_scope_selects_v2_but_single_pointing_does_not():
    blank = {"target_kind": "FIXED", "geometry": "MOSAIC",
             "sources": ["ARCHIVE"]}
    assert should_enable_mosaic_v2_on_scope_change(blank, [])
    assert not should_enable_mosaic_v2_on_scope_change(
        blank | {"geometry": "SINGLE_POINTING"}, [])


@pytest.mark.parametrize("retained,rows", [
    ({"normal_form_version": "2"}, []),
    ({"normal_line_records": "1"}, []),
    ({"spw_rows": ["w123456abcdef"]}, []),
    ({"aggregate_windows": ["line-0"]}, []),
    ({"setup_complete": "on"}, []),
    ({"continuum_setup_declaration": "on"}, []),
    ({"redshift": "0"}, []),
    ({"continuum_redshift": "0.1"}, []),
    ({"representative": "290.420"}, []),
    ({"aggregate": "0.01"}, []),
    ({}, ["w123456abcdef"]),
])
def test_mosaic_switch_never_reinterprets_retained_science(retained, rows):
    values = {"target_kind": "FIXED", "geometry": "MOSAIC"} | retained
    assert not should_enable_mosaic_v2_on_scope_change(values, rows)


@pytest.fixture
def client():
    return create_app({"TESTING": True, "REPORT_DIRECTORY": None}).test_client()


def test_actual_single_pointing_browser_export_keeps_both_sources(client):
    data = continuum_form()
    data["action"] = "download"
    result = client.post("/proposed", data=data)
    assert result.is_json
    exported = result.get_json()
    assert exported["search_options"]["sources"] == ["ARCHIVE", "QUEUE"]
    assert "line_input_contract" not in exported["request"]
    assert exported["request"]["intents"] == ["CONTINUUM"]


def test_actual_blank_mosaic_scope_uses_archive_and_v2(client):
    data = MultiDict([
        ("setup_id", "setup-1"), ("target_kind", "FIXED"),
        ("geometry", "MOSAIC"), ("sources", "ARCHIVE"),
        ("sources", "QUEUE"), ("action", "scope"),
    ])
    response = client.post("/proposed", data=data)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="normal_form_version" value="2"' in html
    assert 'name="sources" value="ARCHIVE"' in html
    assert 'name="sources" value="QUEUE"' not in html


def test_actual_populated_single_to_mosaic_scope_does_not_upgrade(client):
    data = continuum_form()
    data["geometry"] = "MOSAIC"
    data["action"] = "scope"
    response = client.post("/proposed", data=data)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="normal_form_version"' not in html
    assert 'name="normal_line_records"' not in html
