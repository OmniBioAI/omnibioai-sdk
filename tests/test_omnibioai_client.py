"""
tests/test_omnibioai_client.py

Unit tests for omnibioai/client.py::OmniBioAI (construction, base_url/
auth_url handling, token property reflection) and omnibioai/_base.py::
BaseServiceClient's request layer end-to-end against a mocked HTTP call.
"""
from __future__ import annotations

import responses

from omnibioai import OmniBioAI
from omnibioai._base import BaseServiceClient


class TestOmniBioAIConstruction:
    def test_defaults(self):
        c = OmniBioAI(access_token="tok")
        assert c.access_token == "tok"
        assert c.refresh_token is None
        assert c.base_url == "http://127.0.0.1:8080"

    def test_explicit_args(self):
        c = OmniBioAI(
            access_token="tok", refresh_token="ref",
            base_url="https://api.example.com/", auth_url="https://auth.example.com/",
            timeout=15,
        )
        assert c.refresh_token == "ref"
        assert c.base_url == "https://api.example.com"  # trailing slash stripped
        assert c.session.auth_url == "https://auth.example.com"
        assert c.timeout == 15

    def test_session_shares_the_same_token_pair_instance(self):
        """A refresh triggered through client.session must be visible via
        client.access_token immediately -- both must read the same
        TokenPair, not independent copies."""
        c = OmniBioAI(access_token="tok")
        assert c.session.tokens is c.tokens
        c.session.tokens.access_token = "refreshed"
        assert c.access_token == "refreshed"


class TestBaseServiceClientIntegration:
    """End-to-end through BaseServiceClient using OmniBioAI's own
    AuthenticatedSession, proving the pieces wire together correctly."""

    @responses.activate
    def test_successful_request_returns_parsed_json(self):
        c = OmniBioAI(access_token="tok", base_url="https://gw.example.com")
        sub = BaseServiceClient(base_url=c.base_url, session=c.session)
        responses.add(
            responses.GET, "https://gw.example.com/rag/v1/query",
            json={"answer": "42"}, status=200,
        )
        result = sub._request("GET", "/rag/v1/query")
        assert result == {"answer": "42"}

    @responses.activate
    def test_url_joining_handles_leading_and_trailing_slashes(self):
        c = OmniBioAI(access_token="tok", base_url="https://gw.example.com/")
        sub = BaseServiceClient(base_url=c.base_url, session=c.session)
        responses.add(
            responses.GET, "https://gw.example.com/rag/v1/query",
            json={"ok": True}, status=200,
        )
        result = sub._request("GET", "rag/v1/query")
        assert result == {"ok": True}
