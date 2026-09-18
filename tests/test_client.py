"""Unit tests for the legacy omnibioai_sdk.OmniClient: constructor defaults (hardcoded,
env-derived and explicit), the headers property, and objects_list()/object_get() against
mocked HTTP responses.

Developer:
    Manish Kumar <manish@omnibioai.org>
"""

from __future__ import annotations

import pytest
import requests
import responses

from omnibioai_sdk import OmniClient

BASE = "http://127.0.0.1:8001"
OID = "56d3fc3a-709b-4ed0-bf17-8cb73c6746b0"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    """Strip every OmniBioAI env var so tests are hermetic."""
    for var in ("OMNIBIOAI_BASE_URL", "OMNIBIOAI_TOKEN"):
        monkeypatch.delenv(var, raising=False)


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_client_hardcoded_defaults():
    """With no arguments and no env vars set, OmniClient defaults to base_url
    http://127.0.0.1:8001, token dev and timeout 60."""
    c = OmniClient()
    assert c.base_url == "http://127.0.0.1:8001"
    assert c.token == "dev"
    assert c.timeout == 60


def test_client_defaults_from_env(monkeypatch: pytest.MonkeyPatch):
    """OMNIBIOAI_BASE_URL and OMNIBIOAI_TOKEN env vars are read into base_url and token
    when no explicit arguments are given."""
    monkeypatch.setenv("OMNIBIOAI_BASE_URL", BASE)
    monkeypatch.setenv("OMNIBIOAI_TOKEN", "envtoken")
    c = OmniClient()
    assert c.base_url == BASE
    assert c.token == "envtoken"


def test_client_explicit_args():
    """Explicit base_url, token and timeout arguments override env vars and defaults."""
    c = OmniClient(base_url=BASE, token="mytoken", timeout=10)
    assert c.base_url == BASE
    assert c.token == "mytoken"
    assert c.timeout == 10


def test_client_strips_trailing_slash():
    """A trailing slash on base_url is stripped."""
    c = OmniClient(base_url="http://127.0.0.1:8001/")
    assert c.base_url == "http://127.0.0.1:8001"


# ── headers ───────────────────────────────────────────────────────────────────

def test_headers_property():
    """headers returns {'Authorization': 'Bearer <token>'}."""
    c = OmniClient(base_url=BASE, token="tok")
    assert c.headers == {"Authorization": "Bearer tok"}


# ── objects_list ──────────────────────────────────────────────────────────────

@responses.activate
def test_objects_list_success():
    """objects_list() returns the parsed count and items, and sends the token as a
    Bearer Authorization header."""
    c = OmniClient(base_url=BASE, token="dev", timeout=3)
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/objects/",
        json={"count": 2, "items": [{"object_id": "a"}, {"object_id": "b"}]},
        status=200,
    )
    out = c.objects_list()
    assert out["count"] == 2
    assert len(out["items"]) == 2
    assert responses.calls[0].request.headers["Authorization"] == "Bearer dev"


@responses.activate
def test_objects_list_401_raises():
    """objects_list() raises requests.HTTPError for a 401 response."""
    c = OmniClient(base_url=BASE, token="bad")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/", json={}, status=401)
    with pytest.raises(requests.HTTPError):
        c.objects_list()


@responses.activate
def test_objects_list_500_raises():
    """objects_list() raises requests.HTTPError for a 500 response."""
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/", json={}, status=500)
    with pytest.raises(requests.HTTPError):
        c.objects_list()


# ── object_get ────────────────────────────────────────────────────────────────

@responses.activate
def test_object_get_success():
    """object_get() returns the object's type and metadata."""
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/objects/{OID}/",
        json={"object_type": "LiteratureStudy", "metadata": {"study": "X"}},
        status=200,
    )
    obj = c.object_get(OID)
    assert obj["object_type"] == "LiteratureStudy"
    assert obj["metadata"]["study"] == "X"


@responses.activate
def test_object_get_404_raises():
    """object_get() raises requests.HTTPError for a 404 response."""
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/missing/", json={}, status=404)
    with pytest.raises(requests.HTTPError):
        c.object_get("missing")
