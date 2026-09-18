"""
tests/test_omnibioai_client.py

Unit tests for omnibioai/client.py::OmniBioAI (construction, base_url/
auth_url handling, token property reflection) and omnibioai/_base.py::
BaseServiceClient's request layer end-to-end against a mocked HTTP call.

Developer:
    Manish Kumar <manish@omnibioai.org>
"""
from __future__ import annotations

import responses

from omnibioai import OmniBioAI
from omnibioai._base import BaseServiceClient


class TestOmniBioAIConstruction:
    """OmniBioAI's construction: default base_url and refresh_token, explicit argument
    handling including trailing-slash stripping, and that the client and its session
    share one TokenPair."""
    def test_defaults(self):
        """With only an access_token given, refresh_token is None and base_url defaults
        to http://127.0.0.1:8080."""
        c = OmniBioAI(access_token="tok")
        assert c.access_token == "tok"
        assert c.refresh_token is None
        assert c.base_url == "http://127.0.0.1:8080"

    def test_explicit_args(self):
        """Explicit refresh_token, base_url, auth_url and timeout are all applied, with
        trailing slashes stripped from base_url and auth_url."""
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
        """A GET request through _request returns the mocked JSON body."""
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
        """A base_url with a trailing slash and a path with no leading slash still join
        to the correct URL."""
        c = OmniBioAI(access_token="tok", base_url="https://gw.example.com/")
        sub = BaseServiceClient(base_url=c.base_url, session=c.session)
        responses.add(
            responses.GET, "https://gw.example.com/rag/v1/query",
            json={"ok": True}, status=200,
        )
        result = sub._request("GET", "rag/v1/query")
        assert result == {"ok": True}
