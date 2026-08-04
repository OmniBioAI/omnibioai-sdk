"""
tests/test_rag_client.py

Unit tests for omnibioai/rag/client.py::RAGClient -- covers request-shape
correctness (query/kg_stats/kg_entity/kg_drug_disease) against
omnibioai-rag's actual endpoint contract, plus the standard error-mapping
outcomes (dataset.read denied -> PermissionDeniedError, no/invalid token
-> AuthenticationError) at the sub-client level, following the same
`responses`-based mocking style as the rest of this test suite.
"""
from __future__ import annotations

import json

import responses

from omnibioai import OmniBioAI
from omnibioai.exceptions import AuthenticationError, PermissionDeniedError

BASE = "https://gateway.example.com"


def _client():
    return OmniBioAI(access_token="tok", base_url=BASE)


class TestQuery:
    @responses.activate
    def test_minimal_call_sends_expected_payload(self):
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/rag/v1/query",
            json={"documents": [], "summary": {"text": "ok"}}, status=200,
        )
        result = c.rag.query("BRCA1 pathway analysis")

        assert result == {"documents": [], "summary": {"text": "ok"}}
        sent = json.loads(responses.calls[0].request.body)
        assert sent == {
            "query": "BRCA1 pathway analysis",
            "study": "default",
            "mode": "rag",
            "hybrid_search": False,
        }

    @responses.activate
    def test_top_k_omitted_when_not_supplied(self):
        c = _client()
        responses.add(responses.POST, f"{BASE}/rag/v1/query", json={}, status=200)
        c.rag.query("q")
        sent = json.loads(responses.calls[0].request.body)
        assert "top_k" not in sent

    @responses.activate
    def test_top_k_included_when_supplied(self):
        c = _client()
        responses.add(responses.POST, f"{BASE}/rag/v1/query", json={}, status=200)
        c.rag.query("q", top_k=10)
        sent = json.loads(responses.calls[0].request.body)
        assert sent["top_k"] == 10

    @responses.activate
    def test_all_params_forwarded(self):
        c = _client()
        responses.add(responses.POST, f"{BASE}/rag/v1/query", json={}, status=200)
        c.rag.query("q", study="my-study", top_k=3, mode="pmids_only", hybrid_search=True)
        sent = json.loads(responses.calls[0].request.body)
        assert sent == {
            "query": "q", "study": "my-study", "top_k": 3,
            "mode": "pmids_only", "hybrid_search": True,
        }

    @responses.activate
    def test_uses_gateway_rag_prefix(self):
        c = _client()
        responses.add(responses.POST, f"{BASE}/rag/v1/query", json={}, status=200)
        c.rag.query("q")
        assert responses.calls[0].request.url == f"{BASE}/rag/v1/query"

    @responses.activate
    def test_sends_bearer_token(self):
        c = _client()
        responses.add(responses.POST, f"{BASE}/rag/v1/query", json={}, status=200)
        c.rag.query("q")
        assert responses.calls[0].request.headers["Authorization"] == "Bearer tok"

    @responses.activate
    def test_missing_dataset_read_permission_raises_permission_denied(self):
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/rag/v1/query",
            json={"detail": "Insufficient permissions"}, status=403,
        )
        try:
            c.rag.query("q")
            assert False, "expected PermissionDeniedError"
        except PermissionDeniedError as exc:
            assert exc.status_code == 403

    @responses.activate
    def test_invalid_token_raises_authentication_error(self):
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/rag/v1/query",
            json={"detail": "Invalid, expired, or revoked token"}, status=401,
        )
        try:
            c.rag.query("q")
            assert False, "expected AuthenticationError"
        except AuthenticationError:
            pass


class TestKgStats:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/rag/v1/kg/stats",
            json={"nodes": 100}, status=200,
        )
        result = c.rag.kg_stats()
        assert result == {"nodes": 100}


class TestKgEntity:
    @responses.activate
    def test_name_only(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/rag/v1/kg/entity",
            json={"results": []}, status=200,
        )
        c.rag.kg_entity("BRCA1")
        assert responses.calls[0].request.url == f"{BASE}/rag/v1/kg/entity?name=BRCA1"

    @responses.activate
    def test_name_and_type(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/rag/v1/kg/entity",
            json={"results": []}, status=200,
        )
        c.rag.kg_entity("BRCA1", type="gene")
        url = responses.calls[0].request.url
        assert "name=BRCA1" in url
        assert "type=gene" in url


class TestKgDrugDisease:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/rag/v1/kg/drug-disease",
            json={"disease": "Cancer", "drugs": [{"drug": "Aspirin"}]}, status=200,
        )
        result = c.rag.kg_drug_disease("Cancer")
        assert result["drugs"] == [{"drug": "Aspirin"}]
        assert responses.calls[0].request.url == f"{BASE}/rag/v1/kg/drug-disease?disease=Cancer"
