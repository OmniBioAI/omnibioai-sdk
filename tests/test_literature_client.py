"""LiteratureClient (public /v1/literature API) and API-key construction:
request shape and Idempotency-Key handling for ask()/studies(), the v1 error
envelope, 402 -> QuotaExceededError, 429 -> RateLimitError with retry_after,
and OmniBioAI's api_key / OMNIBIOAI_API_KEY / argument-validation rules.
"""
from __future__ import annotations

import json
import uuid

import pytest
import responses

from omnibioai import LiteratureClient, OmniBioAI
from omnibioai.exceptions import QuotaExceededError, RateLimitError, ValidationError

BASE = "https://gateway.example.com"
KEY = "omni_sk_" + "a" * 40
URL = f"{BASE}/v1/literature"


def _client():
    return OmniBioAI(api_key=KEY, base_url=BASE)


@responses.activate
def test_ask_sends_payload_key_and_generated_idempotency_key():
    responses.add(responses.POST, f"{URL}/answers", json={"answer": "x"}, status=200)
    assert _client().literature.ask("What does TP53 do?") == {"answer": "x"}
    req = responses.calls[0].request
    assert json.loads(req.body) == {"query": "What does TP53 do?", "study": "default", "mode": "rag",
                                    "hybrid_search": False}
    assert req.headers["Authorization"] == f"Bearer {KEY}"
    uuid.UUID(req.headers["Idempotency-Key"])


@responses.activate
def test_ask_options_and_explicit_idempotency_key():
    responses.add(responses.POST, f"{URL}/answers", json={}, status=200)
    _client().literature.ask("q", study="Oncology", top_k=5, mode="pmids_only", hybrid_search=True,
                             idempotency_key="retry-1")
    req = responses.calls[0].request
    assert json.loads(req.body)["top_k"] == 5
    assert json.loads(req.body)["study"] == "Oncology"
    assert req.headers["Idempotency-Key"] == "retry-1"


@responses.activate
def test_studies():
    responses.add(responses.GET, f"{URL}/studies", json={"studies": ["Oncology"]}, status=200)
    assert _client().literature.studies() == {"studies": ["Oncology"]}


@responses.activate
def test_quota_exceeded():
    responses.add(responses.POST, f"{URL}/answers", status=402, json={
        "error": {"type": "quota_exceeded", "message": "Your organization has used its included answers.",
                  "request_id": "r1"}})
    with pytest.raises(QuotaExceededError) as exc:
        _client().literature.ask("q")
    assert "included answers" in str(exc.value)
    assert isinstance(exc.value, ValidationError) and exc.value.status_code == 402


@responses.activate
def test_rate_limited_with_and_without_retry_after():
    responses.add(responses.POST, f"{URL}/answers", status=429, headers={"Retry-After": "17"},
                  json={"error": {"type": "rate_limit_exceeded", "message": "slow down", "request_id": "r"}})
    responses.add(responses.POST, f"{URL}/answers", status=429, json={"error": {"type": "rate_limit_exceeded"}})
    with pytest.raises(RateLimitError) as first:
        _client().literature.ask("q")
    assert first.value.retry_after == 17 and str(first.value) == "slow down"
    with pytest.raises(RateLimitError) as second:
        _client().literature.ask("q")
    assert second.value.retry_after is None and str(second.value) == "rate_limit_exceeded"


def test_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("OMNIBIOAI_API_KEY", KEY)
    client = OmniBioAI(base_url=BASE)
    assert client.access_token == KEY and client.refresh_token is None
    assert isinstance(client.literature, LiteratureClient)


def test_constructor_argument_rules(monkeypatch):
    monkeypatch.delenv("OMNIBIOAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="either"):
        OmniBioAI(access_token="jwt", api_key=KEY)
    with pytest.raises(ValueError, match="refresh_token"):
        OmniBioAI(api_key=KEY, refresh_token="r")
    with pytest.raises(ValueError, match="required"):
        OmniBioAI()
    assert OmniBioAI(access_token="jwt").access_token == "jwt"
