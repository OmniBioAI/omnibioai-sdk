"""
tests/test_models_client.py

Unit tests for omnibioai/models/client.py::ModelsClient -- covers
request-shape correctness against omnibioai-model-registry's actual
(task-scoped) endpoint contract, and confirms the access token is always
sent even though Phase 1 discovery found several of these read endpoints
enforce no IAM permission today.
"""
from __future__ import annotations

import responses

from omnibioai import OmniBioAI

BASE = "https://gateway.example.com"


def _client():
    return OmniBioAI(access_token="tok", base_url=BASE)


class TestGet:
    @responses.activate
    def test_calls_show_endpoint_with_task_and_ref(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/model-registry/v1/show",
            json={"ok": True, "meta": {"model_name": "esm2"}, "package_dir": "/x"},
            status=200,
        )
        result = c.models.get("celltype_sc", "esm2")

        assert result["meta"]["model_name"] == "esm2"
        url = responses.calls[0].request.url
        assert "task=celltype_sc" in url
        assert "ref=esm2" in url
        assert "verify=False" in url

    @responses.activate
    def test_verify_true_forwarded(self):
        c = _client()
        responses.add(responses.GET, f"{BASE}/model-registry/v1/show", json={}, status=200)
        c.models.get("celltype_sc", "esm2", verify=True)
        assert "verify=True" in responses.calls[0].request.url

    @responses.activate
    def test_sends_bearer_token_even_though_endpoint_may_not_enforce_it(self):
        """Phase 1 discovery: /v1/show enforces no IAM permission today.
        The SDK still always sends the token -- explicit instruction, not
        an accident -- so no SDK change is needed once that gap closes."""
        c = _client()
        responses.add(responses.GET, f"{BASE}/model-registry/v1/show", json={}, status=200)
        c.models.get("celltype_sc", "esm2")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"


class TestResolve:
    @responses.activate
    def test_calls_resolve_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/model-registry/v1/resolve",
            json={"ok": True, "path": "/registry/celltype_sc/esm2/v1"}, status=200,
        )
        result = c.models.resolve("celltype_sc", "esm2")
        assert result["path"] == "/registry/celltype_sc/esm2/v1"
        url = responses.calls[0].request.url
        assert "task=celltype_sc" in url
        assert "ref=esm2" in url

    @responses.activate
    def test_verify_defaults_true(self):
        c = _client()
        responses.add(responses.GET, f"{BASE}/model-registry/v1/resolve", json={}, status=200)
        c.models.resolve("celltype_sc", "esm2")
        assert "verify=True" in responses.calls[0].request.url


class TestList:
    @responses.activate
    def test_no_filters(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/model-registry/v1/models",
            json={"models": []}, status=200,
        )
        c.models.list()
        assert responses.calls[0].request.url == f"{BASE}/model-registry/v1/models"

    @responses.activate
    def test_task_filter_only(self):
        c = _client()
        responses.add(responses.GET, f"{BASE}/model-registry/v1/models", json={"models": []}, status=200)
        c.models.list(task="celltype_sc")
        url = responses.calls[0].request.url
        assert "task=celltype_sc" in url
        assert "model_name" not in url
        assert "metric_gte" not in url

    @responses.activate
    def test_all_filters(self):
        c = _client()
        responses.add(responses.GET, f"{BASE}/model-registry/v1/models", json={"models": []}, status=200)
        c.models.list(task="celltype_sc", model_name="esm2", metric_gte="accuracy:0.9")
        url = responses.calls[0].request.url
        assert "task=celltype_sc" in url
        assert "model_name=esm2" in url
        assert "metric_gte=accuracy" in url  # ':' gets percent-encoded in the query string
