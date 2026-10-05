"""AQ acquisition contract exercised without external network access."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest
import requests

from alma_duplicate.archive_array_evidence import ArchiveArrayCatalogMode
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient, ArchiveAqError

BASE = "https://almascience.eso.org/aq/service/api/search"
MEMBER = "uid://A001/X123/X456"
OTHER = "uid://A001/X123/X789"
SECRET = "test-ephemeral-key"


def hit(member=MEMBER, name="science", label="7m"):
    return {"_id": f"{member}.source.{name}",
            "_source": {"mous": member, "sourceName": name, "array": label}}


def response(hits=None):
    hits = [hit()] if hits is None else hits
    return {"timed_out": False, "_shards": {"failed": 0},
            "hits": {"total": {"value": len(hits), "relation": "eq"}, "hits": hits}}


class Reply:
    def __init__(self, payload, status=200):
        self.status_code = status
        self.content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()


class Http:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def http_for(payload, properties=None):
    return Http(Reply(properties or {"elasticsearchUrl": BASE}), Reply(payload))


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    monkeypatch.setattr(requests.sessions.Session, "request",
                        lambda *a, **k: pytest.fail("unexpected external HTTP"))


def test_all_sources_queries_and_zero_hits_have_provenance():
    data = response([hit(), hit(name="calibrator", label="12m 7m")])
    http = Http(Reply({"elasticsearchUrl": BASE}), Reply(data), Reply(response([])))
    client = ArchiveAqClient(request=http)
    assert not http.calls
    result = client.fetch_members([MEMBER, MEMBER, OTHER])
    assert result.catalog.provenance.mode is ArchiveArrayCatalogMode.LIVE
    assert result.catalog.manifest_sha256 is None
    assert result.catalog.input_paths == ()
    assert [r.source_name for r in result.catalog.records] == ["science", "calibrator"]
    assert [q.total_hits for q in result.queries] == [2, 0]
    assert [q.member_ous_uid for q in result.queries] == [MEMBER, OTHER]
    assert result.queries[0].response_sha256 == hashlib.sha256(json.dumps(data).encode()).hexdigest()
    assert result.catalog.records[0].response_sha256 == result.queries[0].response_sha256
    assert result.catalog.records[0].retrieved_at == result.queries[0].retrieved_at
    assert result.queries[0].retrieved_at.endswith("+00:00")
    assert len(http.calls) == 3
    for method, url, options in http.calls:
        assert options["allow_redirects"] is False
        assert options["timeout"] == (10, 60)
        assert "Authorization" not in options["headers"]
        if method == "POST":
            assert url == BASE + "/observations/_search"
            assert options["json"]["size"] == 100
            assert options["json"]["track_total_hits"] is True
    assert http.calls[1][2]["json"]["query"] == {"term": {"mous": MEMBER}}
    assert http.calls[2][2]["json"]["query"] == {"term": {"mous": OTHER}}


def test_optional_key_is_sent_only_to_validated_endpoint_not_retained():
    http = http_for(response(), {"elasticsearchUrl": BASE, "elasticsearchApiKey": SECRET})
    result = ArchiveAqClient(request=http).fetch_members([MEMBER])
    assert http.calls[1][2]["headers"]["Authorization"] == "ApiKey " + SECRET
    assert SECRET not in repr(result)
    assert SECRET not in json.dumps(asdict(result))


@pytest.mark.parametrize("url", [
    "http://almascience.eso.org/aq/service/api/search",
    "https://almascience.eso.org.evil.example/aq/service/api/search",
    "https://user:password@almascience.eso.org/aq/service/api/search",
    BASE.replace(".org/", ".org:8443/"), BASE + "?key=" + SECRET,
    BASE + "#fragment", BASE.replace("/api/search", "/../search"),
    BASE.replace("/api/search", "/api/%73earch"), " " + BASE, None,
])
def test_invalid_discovery_is_rejected_before_post(url):
    http = Http(Reply({"elasticsearchUrl": url, "elasticsearchApiKey": SECRET}))
    with pytest.raises(ArchiveAqError) as error:
        ArchiveAqClient(request=http).fetch_members([MEMBER])
    assert error.value.code == "DISCOVERY_INVALID"
    assert SECRET not in str(error.value)
    assert len(http.calls) == 1


@pytest.mark.parametrize("change", [
    lambda p: p["hits"]["total"].update(value=143),
    lambda p: p["hits"]["total"].update(relation="gte"),
    lambda p: p.update(timed_out=True),
    lambda p: p["_shards"].update(failed=1),
    lambda p: p.pop("timed_out"), lambda p: p.pop("_shards"),
    lambda p: p["hits"]["total"].update(value=True),
    lambda p: p["_shards"].update(failed=False),
    lambda p: p.update(terminated_early=True),
])
def test_incomplete_or_malformed_completeness_never_returns_catalog(change):
    data = response()
    change(data)
    with pytest.raises(ArchiveAqError) as error:
        ArchiveAqClient(request=http_for(data)).fetch_members([MEMBER])
    assert error.value.code in {"INCOMPLETE", "RESPONSE_INVALID"}


@pytest.mark.parametrize("bad_hit", [
    hit(member=OTHER), {}, {"_id": "x", "_source": []},
    hit(name=""), hit(label=[]), {"_id": "", "_source": hit()["_source"]},
])
def test_malformed_or_wrong_member_sources_are_rejected(bad_hit):
    with pytest.raises(ArchiveAqError, match="RESPONSE_INVALID"):
        ArchiveAqClient(request=http_for(response([bad_hit]))).fetch_members([MEMBER])


@pytest.mark.parametrize("label", [None, "", "future-array"])
def test_missing_or_unknown_label_is_preserved_for_binder(label):
    result = ArchiveAqClient(request=http_for(response([hit(label=label)]))).fetch_members([MEMBER])
    assert result.catalog.records[0].raw_label == label


def test_duplicate_sources_are_not_silently_selected_or_deduplicated():
    result = ArchiveAqClient(request=http_for(response([hit(), hit()]))).fetch_members([MEMBER])
    assert len(result.catalog.records) == 2


@pytest.mark.parametrize("stage", [0, 1])
@pytest.mark.parametrize("failure,code", [
    (Reply({}, 302), "HTTP_ERROR"), (Reply({}, 500), "HTTP_ERROR"),
    (Reply(SECRET.encode()), "JSON_INVALID"),
    (Reply(b'{"x":1,"x":2}'), "JSON_INVALID"),
    (requests.Timeout(SECRET), "TRANSPORT_ERROR"),
    (requests.ConnectionError(SECRET), "TRANSPORT_ERROR"),
])
def test_errors_are_explicit_and_do_not_echo_secrets(stage, failure, code):
    http = Http(*([Reply({"elasticsearchUrl": BASE, "elasticsearchApiKey": SECRET})] if stage else []), failure)
    with pytest.raises(ArchiveAqError) as error:
        ArchiveAqClient(request=http).fetch_members([MEMBER])
    assert error.value.code == code
    assert SECRET not in str(error.value)
    assert error.value.__suppress_context__
    assert len(http.calls) == stage + 1


def test_later_member_failure_does_not_return_partial_success():
    http = Http(Reply({"elasticsearchUrl": BASE}), Reply(response()), Reply({}, 503))
    with pytest.raises(ArchiveAqError) as error:
        ArchiveAqClient(request=http).fetch_members([MEMBER, OTHER])
    assert error.value.member_ous_uid == OTHER


def test_empty_input_has_no_discovery_or_network():
    http = Http()
    result = ArchiveAqClient(request=http).fetch_members([])
    assert not http.calls and not result.queries and not result.catalog.records


@pytest.mark.parametrize("members", [MEMBER, [MEMBER, "bad"], [None]])
def test_invalid_members_are_rejected_before_network(members):
    http = Http()
    with pytest.raises(ValueError):
        ArchiveAqClient(request=http).fetch_members(members)
    assert not http.calls


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_limit(limit):
    with pytest.raises(ValueError):
        ArchiveAqClient(max_hits=limit)


@pytest.mark.parametrize("key", [123, "secret\nheader", "secret key"])
def test_invalid_optional_credentials_fail_before_post(key):
    http = Http(Reply({"elasticsearchUrl": BASE, "elasticsearchApiKey": key}))
    with pytest.raises(ArchiveAqError, match="DISCOVERY_INVALID"):
        ArchiveAqClient(request=http).fetch_members([MEMBER])
    assert len(http.calls) == 1


def test_configured_limit_and_explicit_https_port():
    http = http_for(response(), {"elasticsearchUrl": BASE.replace(".org/", ".org:443/") + "/"})
    result = ArchiveAqClient(request=http, max_hits=1).fetch_members([MEMBER])
    assert http.calls[1][2]["json"]["size"] == 1
    assert result.queries[0].max_hits == 1


def test_captured_official_response_bytes_replay_through_http_interface():
    from alma_duplicate.archive_array_evidence import load_archive_array_catalog

    folder = Path(__file__).parents[1] / "fixtures/archive/array_evidence_2026_10_01/supporting"
    manifest = folder / "aq-manifest.json"
    entries = json.loads(manifest.read_bytes())
    members = [e["request_body"]["query"]["term"]["mous"] for e in entries]
    http = Http(Reply({"elasticsearchUrl": BASE}),
                *(Reply((folder / e["file"]).read_bytes()) for e in entries))
    result = ArchiveAqClient(request=http).fetch_members(members)
    captured = load_archive_array_catalog(manifest)
    # Replaying bytes here verifies protocol compatibility, not a live service call.
    identity = lambda r: (r.observation_id, r.member_ous_uid, r.source_name, r.raw_label, r.response_sha256)
    assert [identity(r) for r in result.catalog.records] == [identity(r) for r in captured.records]
    assert len(result.queries) == 5
