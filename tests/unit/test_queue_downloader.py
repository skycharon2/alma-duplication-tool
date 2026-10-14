"""Default test suite does not contact the ALMA service."""

from datetime import UTC, datetime
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from alma_duplicate.clients.queue_downloader import (
    DownloadedQueue, QueueDownloadError, _OfficialRedirects,
    download_queue_csv,
)

URL = "https://almascience.eso.org/documents-and-tools/latest/duplication-check-csv"
NOW = datetime(2026, 10, 14, 8, tzinfo=UTC)


class Response(BytesIO):
    def __init__(self, body=b"Queue data,field\na,b\n", headers=None, url=URL, status=200):
        super().__init__(body)
        self.headers = headers or {"Content-Type": "text/csv"}
        self._url, self.status = url, status

    def geturl(self):
        return self._url


class Opener:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


def test_exact_bytes_url_provenance_and_time():
    body = b"\xef\xbb\xbffirst,second\r\n1,2\r\n"
    opener = Opener(Response(body, headers={"Content-Type": "text/csv",
                                            "ETag": '"v1"',
                                            "Last-Modified": "Wed, 14 Oct 2026 08:00:00 GMT"}))
    result = download_queue_csv(opener=opener, clock=lambda: NOW)
    assert result == DownloadedQueue(body, URL, NOW, '"v1"',
                                     "Wed, 14 Oct 2026 08:00:00 GMT")
    request, timeout = opener.requests[0]
    assert request.get_header("Accept-encoding") == "identity"
    assert timeout > 0


@pytest.mark.parametrize("body,headers", [
    (b"", {"Content-Type": "text/csv"}),
    (b"<!DOCTYPE html><html>no</html>", {"Content-Type": "text/csv"}),
    (b"<html>login</html>", {"Content-Type": "text/html"}),
    (b'{"message":"error"}', {"Content-Type": "application/json"}),
    (b"12345", {"Content-Type": "text/csv", "Content-Length": "10000"}),
    (b"12345", {"Content-Type": "text/csv", "Content-Length": "6"}),
    (b"abcde", {"Content-Type": "text/csv", "Content-Length": "bad"}),
    (b"csv", {"Content-Type": "text/csv", "Content-Encoding": "gzip"}),
])
def test_bad_responses_fail_closed(body, headers):
    with pytest.raises(QueueDownloadError):
        download_queue_csv(opener=Opener(Response(body, headers=headers)),
                           max_bytes=16, clock=lambda: NOW)


def test_actual_read_limit_enforced_even_when_length_absent():
    with pytest.raises(QueueDownloadError, match="size limit"):
        download_queue_csv(opener=Opener(Response(b"1234567890")),
                           max_bytes=8, clock=lambda: NOW)


def test_disallowed_final_redirect_origin():
    with pytest.raises(QueueDownloadError, match="approved"):
        download_queue_csv(opener=Opener(Response(url="https://evil.example/queue.csv")),
                           clock=lambda: NOW)


def test_redirect_is_rejected_before_following_it():
    request = Request(URL)
    with pytest.raises(QueueDownloadError, match="approved"):
        _OfficialRedirects().redirect_request(
            request, None, 302, "Found", {}, "https://evil.example/queue.csv")


@pytest.mark.parametrize("bad", [
    "http://almascience.eso.org/documents-and-tools/latest/duplication-check-csv",
    "https://almascience.eso.org.evil.example/documents-and-tools/latest/duplication-check-csv",
    "https://almascience.eso.org:444/documents-and-tools/latest/duplication-check-csv",
    "https://user@almascience.eso.org/documents-and-tools/latest/duplication-check-csv",
    "https://almascience.eso.org/other/resource",
])
def test_bad_initial_url_fails_before_network(bad):
    opener = Opener(Response())
    with pytest.raises(QueueDownloadError):
        download_queue_csv(url=bad, opener=opener, clock=lambda: NOW)
    assert opener.requests == []


@pytest.mark.parametrize("error", [
    HTTPError(URL, 404, "Not Found", {}, None),
    HTTPError(URL, 500, "Server error", {}, None),
    URLError("offline"), TimeoutError("timed out"),
])
def test_network_errors_are_explicit(error):
    with pytest.raises(QueueDownloadError):
        download_queue_csv(opener=Opener(error=error), clock=lambda: NOW)


def test_naive_retrieval_clock_is_refused():
    with pytest.raises(ValueError, match="timezone"):
        download_queue_csv(opener=Opener(Response()),
                           clock=lambda: datetime(2026, 10, 14))
