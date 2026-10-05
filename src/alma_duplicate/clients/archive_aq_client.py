"""Explicit, all-or-nothing acquisition of official AQ Member source records.

Construction performs no I/O. Only fetch_members accesses HTTP; source selection,
array interpretation and scientific evaluation remain with the existing binder.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

import requests

from alma_duplicate.archive_array_evidence import (
    ArchiveArrayCatalog, ArchiveArrayCatalogMode, ArchiveArrayCatalogProvenance,
    ArrayRecord,
)

PROPERTIES_URL = "https://almascience.eso.org/aq/service/api/v1/properties"
_MEMBER = re.compile(r"uid://[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+\Z")


class ArchiveAqError(ValueError):
    """Safe error metadata; never includes response bodies, headers or secrets."""

    def __init__(self, code: str, member_ous_uid: str | None = None):
        self.code = code
        self.member_ous_uid = member_ous_uid
        super().__init__(f"AQ acquisition failed: {code}")


@dataclass(frozen=True)
class ArchiveAqMemberQuery:
    member_ous_uid: str
    url: str
    retrieved_at: str
    response_sha256: str
    total_hits: int
    max_hits: int


@dataclass(frozen=True)
class ArchiveAqFetchResult:
    catalog: ArchiveArrayCatalog
    queries: tuple[ArchiveAqMemberQuery, ...]
    properties_url: str = PROPERTIES_URL


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite JSON literal")


def _endpoint(value):
    # The observed service is an explicit allowlist, not an arbitrary URL prefix.
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("Invalid endpoint")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.hostname != "almascience.eso.org"
            or parsed.port not in (None, 443) or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ("/aq/service/api/search", "/aq/service/api/search/")):
        raise ValueError("Invalid endpoint")
    return "https://almascience.eso.org/aq/service/api/search/observations/_search"


class ArchiveAqClient:
    """Fetch unique Members in input order with injected HTTP for offline tests.

    A successful call returns every hit or raises ArchiveAqError. There are no
    retries, pagination, fallback, disk writes or implicit calls during import.
    The request callable follows requests.request(method, url, **kwargs).
    """

    def __init__(self, *, request=None, max_hits=100):
        if type(max_hits) is not int or max_hits < 1:
            raise ValueError("max_hits must be a positive integer")
        self._request = request if request is not None else requests.request
        self._max_hits = max_hits

    def _read(self, method, url, *, member=None, headers=None, body=None):
        options = {"timeout": (10, 60), "allow_redirects": False,
                   "headers": headers or {"Accept": "application/json"}}
        if body is not None:
            options["json"] = body
        try:
            response = self._request(method, url, **options)
        except requests.RequestException:
            raise ArchiveAqError("TRANSPORT_ERROR", member) from None
        # Do not follow redirects or call raise_for_status, whose exception may
        # retain request headers or response content.
        if response.status_code != 200:
            raise ArchiveAqError("HTTP_ERROR", member) from None
        raw = response.content
        try:
            payload = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
        except (ValueError, UnicodeError, TypeError):
            raise ArchiveAqError("JSON_INVALID", member) from None
        if not isinstance(payload, dict):
            raise ArchiveAqError("RESPONSE_INVALID", member) from None
        return payload, hashlib.sha256(raw).hexdigest(), datetime.now(timezone.utc).isoformat()

    def fetch_members(self, members) -> ArchiveAqFetchResult:
        if isinstance(members, (str, bytes)):
            raise ValueError("members must be an iterable of Member UIDs")
        members = tuple(members)
        if any(not isinstance(m, str) or not _MEMBER.fullmatch(m) for m in members):
            raise ValueError("Invalid Member OUS UID")
        members = tuple(dict.fromkeys(members))
        records, queries = [], []
        if members:
            properties, _, _ = self._read("GET", PROPERTIES_URL)
            try:
                endpoint = _endpoint(properties["elasticsearchUrl"])
                key = properties.get("elasticsearchApiKey")
                if key is not None and (not isinstance(key, str)
                        or any(ord(c) < 33 or ord(c) > 126 for c in key)):
                    raise ValueError("Invalid optional credential")
            except (KeyError, ValueError, TypeError):
                raise ArchiveAqError("DISCOVERY_INVALID") from None
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if key:
                headers["Authorization"] = "ApiKey " + key
            for member in members:
                body = {"size": self._max_hits, "track_total_hits": True,
                        "_source": ["mous", "sourceName", "array"],
                        "query": {"term": {"mous": member}}}
                payload, digest, retrieved = self._read(
                    "POST", endpoint, member=member, headers=headers, body=body)
                hits = self._validate(payload, member)
                for hit in hits:
                    source = hit["_source"]
                    records.append(ArrayRecord(hit["_id"], source["mous"], source["sourceName"],
                                               source.get("array"), digest, retrieved, endpoint))
                queries.append(ArchiveAqMemberQuery(member, endpoint, retrieved, digest,
                                                   len(hits), self._max_hits))
        catalog = ArchiveArrayCatalog(tuple(records),
            ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE))
        return ArchiveAqFetchResult(catalog, tuple(queries))

    def _validate(self, payload, member):
        try:
            hits = payload["hits"]["hits"]
            total = payload["hits"]["total"]
            failed = payload["_shards"]["failed"]
            timed_out = payload["timed_out"]
            if (not isinstance(hits, list) or not isinstance(total, dict)
                    or type(total["value"]) is not int or total["value"] < 0
                    or type(failed) is not int or failed < 0 or type(timed_out) is not bool
                    or type(payload.get("terminated_early", False)) is not bool):
                raise ValueError("Invalid completeness metadata")
            if (timed_out or failed or payload.get("terminated_early", False)
                    or total["relation"] != "eq" or total["value"] != len(hits)
                    or len(hits) > self._max_hits):
                raise ArchiveAqError("INCOMPLETE", member)
            for hit in hits:
                source = hit["_source"]
                values = (hit["_id"], source["mous"], source["sourceName"])
                if (not all(isinstance(v, str) and v.strip() for v in values)
                        or source["mous"] != member
                        or (source.get("array") is not None and not isinstance(source["array"], str))):
                    raise ValueError("Malformed source")
        except ArchiveAqError:
            raise ArchiveAqError("INCOMPLETE", member) from None
        except (KeyError, TypeError, ValueError):
            raise ArchiveAqError("RESPONSE_INVALID", member) from None
        return hits
