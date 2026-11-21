from datetime import date
import pytest
import requests
from meal_insight.connectors.commcare import CommCareAuthError, CommCareClient, CommCareError


class R:
    def __init__(self, status, payload=None):
        self.status_code, self._p = status, payload

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(resps, **kw):
    s = FakeSession(resps)
    return CommCareClient("https://www.commcarehq.org", "demo", "u@x.org", "KEY", session=s, retry_backoff=0, **kw), s


def test_pagination_dedupe_and_filters():
    p1 = {"meta": {"next": "/a/demo/api/v0.5/form/?limit=2&offset=2"}, "objects": [{"id": "a"}, {"id": "b"}]}
    p2 = {"meta": {"next": None}, "objects": [{"id": "b"}, {"id": "c"}]}
    c, s = client([R(200, p1), R(200, p2)])
    out = c.fetch_forms(xmlns="x", start=date(2026, 11, 1), end="2026-11-30T23:59:59")
    assert [r["id"] for r in out] == ["a", "b", "c"]
    url, params, headers = s.calls[0]
    assert params["xmlns"] == "x" and params["received_on_start"] == "2026-11-01T00:00:00"
    assert params["received_on_end"] == "2026-11-30T23:59:59"
    assert headers["Authorization"] == "ApiKey u@x.org:KEY"
    assert s.calls[1][0].startswith("https://www.commcarehq.org/a/demo/api/v0.5/form/") and s.calls[1][1] is None


def test_incremental_since_overrides_start():
    c, s = client([R(200, {"meta": {}, "objects": []})])
    c.fetch_forms(start="2026-01-01", since="2026-11-03T10:00:00")
    assert s.calls[0][1]["received_on_start"] == "2026-11-03T10:00:00"


def test_retry_then_success():
    c, s = client([R(500), requests.Timeout(), R(200, {"meta": {}, "objects": [{"id": 1}]})])
    assert c.fetch_forms() == [{"id": 1}] and len(s.calls) == 3


def test_retries_exhausted():
    c, _ = client([R(503)] * 4)
    with pytest.raises(CommCareError):
        c.fetch_forms()


def test_auth_error_no_retry():
    c, s = client([R(401)])
    with pytest.raises(CommCareAuthError):
        c.test_connection()
    assert len(s.calls) == 1


def test_https_required_and_repr_hides_key():
    with pytest.raises(CommCareError):
        CommCareClient("http://example.org", "d", "u", "k")
    c, _ = client([])
    assert "KEY" not in repr(c)


def test_list_forms():
    apps = {"meta": {}, "objects": [{"name": "App", "modules": [{"name": {"en": "Mod"},
            "forms": [{"name": {"en": "Reg"}, "xmlns": "urn:x"}]}]}]}
    c, _ = client([R(200, apps)])
    assert c.list_forms() == [{"application": "App", "module": "Mod", "formulaire": "Reg", "xmlns": "urn:x"}]
