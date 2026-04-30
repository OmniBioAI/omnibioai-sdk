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
    for var in (
        "OMNIBIOAI_BASE_URL",
        "OMNIBIOAI_TOKEN",
        "OMNIBIOAI_JUPYTER_BASE",
        "OMNIBIOAI_JUPYTER_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)


# ── __init__ ──────────────────────────────────────────────────────────────────

def test_client_hardcoded_defaults():
    c = OmniClient()
    assert c.base_url == "http://127.0.0.1:8001"
    assert c.token == "dev"
    assert c.timeout == 60


def test_client_defaults_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OMNIBIOAI_BASE_URL", BASE)
    monkeypatch.setenv("OMNIBIOAI_TOKEN", "envtoken")
    c = OmniClient()
    assert c.base_url == BASE
    assert c.token == "envtoken"


def test_client_explicit_args():
    c = OmniClient(base_url=BASE, token="mytoken", timeout=10)
    assert c.base_url == BASE
    assert c.token == "mytoken"
    assert c.timeout == 10


def test_client_strips_trailing_slash():
    c = OmniClient(base_url="http://127.0.0.1:8001/")
    assert c.base_url == "http://127.0.0.1:8001"


# ── headers ───────────────────────────────────────────────────────────────────

def test_headers_property():
    c = OmniClient(base_url=BASE, token="tok")
    assert c.headers == {"Authorization": "Bearer tok"}


# ── objects_list ──────────────────────────────────────────────────────────────

@responses.activate
def test_objects_list_success():
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
    c = OmniClient(base_url=BASE, token="bad")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/", json={}, status=401)
    with pytest.raises(requests.HTTPError):
        c.objects_list()


@responses.activate
def test_objects_list_500_raises():
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/", json={}, status=500)
    with pytest.raises(requests.HTTPError):
        c.objects_list()


# ── object_get ────────────────────────────────────────────────────────────────

@responses.activate
def test_object_get_success():
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
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(responses.GET, f"{BASE}/api/dev/objects/missing/", json={}, status=404)
    with pytest.raises(requests.HTTPError):
        c.object_get("missing")


# ── get_launch_urls ───────────────────────────────────────────────────────────

def test_get_launch_urls_default_env():
    c = OmniClient(base_url=BASE, token="dev")
    urls = c.get_launch_urls(OID)
    assert urls["notebook"] == (
        f"http://127.0.0.1:8890/lab?token=devtoken&omnibioai_object_id={OID}"
    )
    assert urls["vscode"] == "vscode://"
    assert urls["rstudio"] == "rstudio://"


def test_get_launch_urls_custom_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OMNIBIOAI_JUPYTER_BASE", "http://jupyter.internal:9000")
    monkeypatch.setenv("OMNIBIOAI_JUPYTER_TOKEN", "secrettoken")
    c = OmniClient(base_url=BASE, token="dev")
    urls = c.get_launch_urls(OID)
    assert urls["notebook"] == (
        f"http://jupyter.internal:9000/lab?token=secrettoken&omnibioai_object_id={OID}"
    )


def test_get_launch_urls_returns_all_keys():
    c = OmniClient(base_url=BASE, token="dev")
    assert set(c.get_launch_urls(OID).keys()) == {"notebook", "vscode", "rstudio"}


# ── get_launcher_url ──────────────────────────────────────────────────────────

def test_get_launcher_url_default_port():
    c = OmniClient(base_url=BASE, token="dev")
    assert c.get_launcher_url(OID) == f"http://127.0.0.1:5190/?object_id={OID}"


def test_get_launcher_url_custom_port():
    c = OmniClient(base_url=BASE, token="dev")
    assert c.get_launcher_url(OID, launcher_port=8080) == f"http://127.0.0.1:8080/?object_id={OID}"


# ── generate_r_script ─────────────────────────────────────────────────────────

@responses.activate
def test_generate_r_script_content():
    c = OmniClient(base_url=BASE, token="mytoken")
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/objects/{OID}/",
        json={"name": "My Dataset", "object_type": "RNASeqObject"},
        status=200,
    )
    script = c.generate_r_script(OID)
    assert "# Object: My Dataset" in script
    assert "# Type:   RNASeqObject" in script
    assert f"# ID:     {OID}" in script
    assert f'OMNIBIOAI_OBJECT_ID = "{OID}"' in script
    assert f'OMNIBIOAI_BASE_URL  = "{BASE}"' in script
    assert 'OMNIBIOAI_TOKEN     = "mytoken"' in script
    assert "library(httr2)" in script
    assert "resp_body_json()" in script


@responses.activate
def test_generate_r_script_missing_name_falls_back():
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/objects/{OID}/",
        json={"object_type": "SomeType"},
        status=200,
    )
    script = c.generate_r_script(OID)
    assert "# Object: Unknown" in script
    assert "# Type:   SomeType" in script


@responses.activate
def test_generate_r_script_missing_object_type_falls_back():
    c = OmniClient(base_url=BASE, token="dev")
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/objects/{OID}/",
        json={"name": "Some Name"},
        status=200,
    )
    script = c.generate_r_script(OID)
    assert "# Object: Some Name" in script
    assert "# Type:   Unknown" in script


# ── generate_python_snippet ───────────────────────────────────────────────────

def test_generate_python_snippet_content():
    c = OmniClient(base_url=BASE, token="mytoken")
    snippet = c.generate_python_snippet(OID)
    assert f'export OMNIBIOAI_OBJECT_ID="{OID}"' in snippet
    assert f'export OMNIBIOAI_BASE_URL="{BASE}"' in snippet
    assert 'export OMNIBIOAI_TOKEN="mytoken"' in snippet
    assert "from omnibioai_sdk import OmniClient" in snippet
    assert "c.object_get" in snippet
