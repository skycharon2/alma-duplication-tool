"""Explicit, all-or-nothing acquisition of official AQ Member source records.

Construction performs no I/O. Only fetch_members accesses HTTP; source selection,
array interpretation and scientific evaluation remain with the existing binder.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, nullcontext
from contextvars import copy_context
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from alma_duplicate.archive_endpoints import (
    ARCHIVE_ORIGINS, aq_search_endpoint, request_timeout, validate_origins,
)

import requests

from alma_duplicate.progress import emit_progress
from alma_duplicate.performance import measure_stage

from alma_duplicate.archive_array_evidence import (
    ArchiveArrayCatalog, ArchiveArrayCatalogMode, ArchiveArrayCatalogProvenance,
    ArrayRecord,
)

PROPERTIES_URL = "https://almascience.eso.org/aq/service/api/v1/properties"
_MEMBER = re.compile(r"uid://[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+\Z")


class ArchiveAqError(ValueError):
    """Safe error metadata; never includes response bodies, headers or secrets."""

    def __init__(self, code: str, member_ous_uid: str | None = None, *, http_status=None, attempts=(), details=None):
        self.details = details or {}
        self.http_status = http_status
        self.attempts = attempts
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
    request_sizes: tuple[int, ...] = ()


@dataclass(frozen=True)
class ArchiveAqFetchResult:
    catalog: ArchiveArrayCatalog
    queries: tuple[ArchiveAqMemberQuery, ...]
    properties_url: str = PROPERTIES_URL
    mirror_attempts: tuple[dict, ...] = ()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-finite JSON literal")


def _endpoint(value, *, origin=ARCHIVE_ORIGINS[0]):
    # Discovery credentials never cross to another mirror or arbitrary host.
    return aq_search_endpoint(value, origin=origin)


class ArchiveAqClient:
    """Fetch unique Members in input order with injected HTTP for offline tests.

    A successful call returns every hit or raises ArchiveAqError. There are no
    pagination, disk writes or implicit calls during import. A clean truncated
    response may trigger one bounded full refetch; partial responses are never merged.
    The request callable follows requests.request(method, url, **kwargs).
    """

    def __init__(self, *, request=None, max_hits=100, max_member_hits=10000, origin=ARCHIVE_ORIGINS[0], member_workers=1,
                 group_size=1):
        if type(member_workers) is not int or member_workers not in (1, 2):
            raise ValueError("AQ member workers must be 1 or 2")
        self._member_workers = member_workers
        if type(group_size) is not int or not 1 <= group_size <= 32:
            raise ValueError("AQ group size must be an integer between 1 and 32")
        self._group_size = group_size
        if type(max_hits) is not int or max_hits < 1:
            raise ValueError("max_hits must be a positive integer")
        if type(max_member_hits) is not int or max_member_hits < max_hits:
            raise ValueError("max_member_hits must be an integer at least max_hits")
        self._max_member_hits = max_member_hits
        self.origin = validate_origins((origin,))[0]
        self.properties_url = self.origin + "/aq/service/api/v1/properties"
        self._request = request
        self._max_hits = max_hits

    def _read(self, request, method, url, *, member=None, headers=None, body=None):
        options = {"timeout": request_timeout(), "allow_redirects": False,
                   "headers": headers or {"Accept": "application/json"}}
        if body is not None:
            options["json"] = body
        try:
            response = request(method, url, **options)
        except requests.RequestException:
            raise ArchiveAqError("TRANSPORT_ERROR", member) from None
        # Do not follow redirects or call raise_for_status, whose exception may
        # retain request headers or response content.
        if response.status_code != 200:
            raise ArchiveAqError("HTTP_ERROR", member, http_status=response.status_code) from None
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
        if not members:
            return self._fetch_members(members, None)

        with ExitStack() as scope:
            def open_transport():
                if self._request is not None:
                    return self._request
                session = scope.enter_context(requests.Session())

                def request(method, url, **options):
                    session.cookies.clear()
                    return session.request(method, url, **options)

                return request

            request = open_transport()
            sibling_request = open_transport() if self._member_workers == 2 and len(members) > 1 else None
            return self._fetch_members(members, request, sibling_request)

    def _fetch_members(self, members, request, sibling_request=None):
        records, queries = [], []
        emit_progress("aq", 0, len(members), "members")
        if members:
            with measure_stage('aq_discovery'):
                properties, _, _ = self._read(request, "GET", self.properties_url)
            try:
                endpoint = _endpoint(properties["elasticsearchUrl"], origin=self.origin)
                key = properties.get("elasticsearchApiKey")
                if key is not None and (not isinstance(key, str)
                        or any(ord(c) < 33 or ord(c) > 126 for c in key)):
                    raise ValueError("Invalid optional credential")
            except (KeyError, ValueError, TypeError):
                raise ArchiveAqError("DISCOVERY_INVALID") from None
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if key:
                headers["Authorization"] = "ApiKey " + key
            for member_records, query in self._member_results(members, request, sibling_request, endpoint, headers):
                records.extend(member_records)
                queries.append(query)
                emit_progress("aq", len(queries), len(members), "members")
        catalog = ArchiveArrayCatalog(tuple(records),
            ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE))
        return ArchiveAqFetchResult(catalog, tuple(queries), self.properties_url)

    def _member_results(self, members, request, sibling_request, endpoint, headers):
        if self._group_size == 1:
            yield from self._individual_results(members, request, sibling_request, endpoint, headers)
            return
        for offset in range(0, len(members), self._group_size):
            group = members[offset:offset + self._group_size]
            if len(group) == 1:
                yield self._fetch_member(request, endpoint, headers, group[0])
                continue
            try:
                with measure_stage('aq_group'):
                    results = self._fetch_group(request, endpoint, headers, group)
            except ArchiveAqError:
                with measure_stage('aq_group_fallback'):
                    yield from self._individual_results(group, request, sibling_request, endpoint, headers)
            else:
                yield from results

    def _individual_results(self, members, request, sibling_request, endpoint, headers):
        executor_scope = ThreadPoolExecutor(max_workers=1) if sibling_request else nullcontext()
        with executor_scope as executor:
            step = 2 if executor else 1
            for index in range(0, len(members), step):
                sibling = None
                if executor and index + 1 < len(members):
                    sibling = executor.submit(copy_context().run, self._fetch_member,
                                              sibling_request, endpoint, headers, members[index + 1])
                results = [self._fetch_member(request, endpoint, headers, members[index])]
                if sibling is not None:
                    results.append(sibling.result())
                yield from results

    def _fetch_group(self, request, endpoint, headers, members):
        limit = min(10000, self._max_hits * len(members))
        payload, digest, retrieved = self._read(request, 'POST', endpoint, headers=headers, body={
            'size': limit, 'track_total_hits': True, '_source': ['mous', 'sourceName', 'array'],
            'query': {'terms': {'mous': list(members)}},
        })
        hits = self._validate(payload, None, limit=limit, group=set(members))
        grouped = {member: [] for member in members}
        for hit in hits:
            source = hit['_source']
            member = source['mous']
            grouped[member].append(ArrayRecord(hit['_id'], member, source['sourceName'],
                                              source.get('array'), digest, retrieved, endpoint))
        if any(len(records) > self._max_member_hits for records in grouped.values()):
            raise ArchiveAqError('INCOMPLETE')
        return [(records, ArchiveAqMemberQuery(member, endpoint, retrieved, digest,
                                               len(records), limit, (limit,)))
                for member, records in grouped.items()]


    def _fetch_member(self, request, endpoint, headers, member):
        body = {"size": self._max_hits, "track_total_hits": True,
                "_source": ["mous", "sourceName", "array"],
                "query": {"term": {"mous": member}}}
        with measure_stage('aq_member'):
            payload, digest, retrieved = self._read(
                request, "POST", endpoint, member=member, headers=headers, body=body)
            sizes = [self._max_hits]
            try:
                hits = self._validate(payload, member)
            except ArchiveAqError as exc:
                details = exc.details
                # Only an otherwise clean, exactly capped response warrants
                # expansion. Discard it and validate one complete response.
                if (exc.code != 'INCOMPLETE'
                        or set(details.get('reasons', [])) != {'HIT_COUNT_MISMATCH', 'HIT_LIMIT_EXCEEDED'}
                        or details.get('returned_hits') != self._max_hits
                        or not self._max_hits < details.get('total_hits', 0) <= self._max_member_hits):
                    raise
                expected = details['total_hits']
                sizes.append(expected)
                payload, digest, retrieved = self._read(
                    request, 'POST', endpoint, member=member, headers=headers, body={**body, 'size': expected})
                hits = self._validate(payload, member, limit=expected)
                if len(hits) != expected:
                    raise ArchiveAqError('INCOMPLETE', member, details={
                        'reasons': ['TOTAL_CHANGED'], 'total_hits': len(hits),
                        'returned_hits': len(hits), 'max_hits': expected})
        records = [
            ArrayRecord(hit["_id"], member, hit["_source"]["sourceName"],
                        hit["_source"].get("array"), digest, retrieved, endpoint)
            for hit in hits
        ]
        return records, ArchiveAqMemberQuery(member, endpoint, retrieved, digest,
                                             len(hits), sizes[-1], tuple(sizes))

    def _validate(self, payload, member, *, limit=None, group=None):
        limit = self._max_hits if limit is None else limit
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
            reasons = []
            if timed_out:
                reasons.append('TIMED_OUT')
            if failed:
                reasons.append('FAILED_SHARDS')
            if payload.get('terminated_early', False):
                reasons.append('TERMINATED_EARLY')
            if total['relation'] != 'eq':
                reasons.append('TOTAL_NOT_EXACT')
            if total['value'] != len(hits):
                reasons.append('HIT_COUNT_MISMATCH')
            if total['value'] > limit or len(hits) > limit:
                reasons.append('HIT_LIMIT_EXCEEDED')
            if reasons:
                raise ArchiveAqError('INCOMPLETE', member, details={
                    'reasons': reasons, 'total_hits': total['value'],
                    'returned_hits': len(hits), 'max_hits': limit})
            for hit in hits:
                source = hit["_source"]
                values = (hit["_id"], source["mous"], source["sourceName"])
                if (not all(isinstance(v, str) and v.strip() for v in values)
                        or (source["mous"] != member if group is None else source["mous"] not in group)
                        or (source.get("array") is not None and not isinstance(source["array"], str))):
                    raise ValueError("Malformed source")
        except ArchiveAqError:
            raise
        except (KeyError, TypeError, ValueError):
            raise ArchiveAqError("RESPONSE_INVALID", member) from None
        return hits
