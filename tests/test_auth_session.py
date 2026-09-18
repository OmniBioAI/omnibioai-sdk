"""
tests/test_auth_session.py

Unit tests for omnibioai/auth/session.py::AuthenticatedSession -- token
refresh on 401 (success and failure paths), the single-retry-only
guarantee, and X-Trace-Id propagation.

Developer:
    Manish Kumar <manish@omnibioai.org>
"""
from __future__ import annotations

import pytest
import requests
import responses

from omnibioai.auth.session import AuthenticatedSession
from omnibioai.auth.tokens import TokenPair
from omnibioai.exceptions import AuthenticationError

AUTH_URL = "https://auth.omnibioai.example"
TARGET_URL = "https://gateway.omnibioai.example/rag/v1/query"


def _session(refresh_token="refresh-1"):
    """An AuthenticatedSession with a fresh TokenPair and the module's AUTH_URL,
    defaulting to a real refresh token."""
    tokens = TokenPair(access_token="access-1", refresh_token=refresh_token)
    return AuthenticatedSession(tokens=tokens, auth_url=AUTH_URL, timeout=5)


class TestAuthHeaderInjection:
    """Every request carries the session's current access token as a Bearer
    Authorization header."""
    @responses.activate
    def test_authorization_header_uses_current_access_token(self):
        """A request's Authorization header is 'Bearer <access token>' for the session's
        current token."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)
        s.request("GET", TARGET_URL)
        assert responses.calls[0].request.headers["Authorization"] == "Bearer access-1"


class TestTraceIdPropagation:
    """X-Trace-Id is generated when the caller doesn't supply one, used verbatim when
    they do, and unique across separate calls by default."""
    @responses.activate
    def test_trace_id_generated_when_not_supplied(self):
        """With no trace_id argument, a non-empty X-Trace-Id header is sent and recorded
        as last_trace_id."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)
        s.request("GET", TARGET_URL)
        sent = responses.calls[0].request.headers["X-Trace-Id"]
        assert sent
        assert s.last_trace_id == sent

    @responses.activate
    def test_trace_id_caller_supplied_is_used_verbatim(self):
        """A caller-supplied trace_id is sent as X-Trace-Id verbatim and recorded as
        last_trace_id."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)
        s.request("GET", TARGET_URL, trace_id="my-trace-id")
        assert responses.calls[0].request.headers["X-Trace-Id"] == "my-trace-id"
        assert s.last_trace_id == "my-trace-id"

    @responses.activate
    def test_trace_id_unique_across_calls_by_default(self):
        """Two calls with no explicit trace_id get different auto-generated X-Trace-Id
        values."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)
        s.request("GET", TARGET_URL)
        first = responses.calls[0].request.headers["X-Trace-Id"]
        s.request("GET", TARGET_URL)
        second = responses.calls[1].request.headers["X-Trace-Id"]
        assert first != second


class TestRefreshOnUnauthorized:
    """AuthenticatedSession's 401 handling: refreshing tokens and retrying once on
    success, never retrying a second time, and raising AuthenticationError on every
    refresh failure mode."""
    @responses.activate
    def test_401_triggers_refresh_and_retries_once(self):
        """A 401 triggers exactly one refresh call and one retry with the new access
        token, for a total of 3 HTTP calls, and returns the retried 200 response."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            json={"access_token": "access-2", "refresh_token": "refresh-2"}, status=200,
        )
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)

        result = s.request("GET", TARGET_URL)

        assert result.status_code == 200
        assert result.json() == {"ok": True}
        assert s.tokens.access_token == "access-2"
        assert s.tokens.refresh_token == "refresh-2"
        # 1st attempt (401) + refresh call + retry = 3 total HTTP calls
        assert len(responses.calls) == 3
        # The retried request must use the NEW access token.
        assert responses.calls[2].request.headers["Authorization"] == "Bearer access-2"

    @responses.activate
    def test_second_401_after_refresh_does_not_loop(self):
        """If the retried request also comes back 401, AuthenticatedSession
        must not attempt a second refresh -- the caller (BaseServiceClient)
        sees the final 401 response and raises AuthenticationError from
        there instead."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            json={"access_token": "access-2"}, status=200,
        )
        responses.add(responses.GET, TARGET_URL, json={"detail": "still invalid"}, status=401)

        result = s.request("GET", TARGET_URL)

        assert result.status_code == 401
        assert len(responses.calls) == 3  # no third GET attempt

    @responses.activate
    def test_no_refresh_token_skips_refresh_entirely(self):
        """With no refresh token held, a 401 is returned as-is with no refresh attempt
        at all (1 HTTP call)."""
        s = _session(refresh_token=None)
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)

        result = s.request("GET", TARGET_URL)

        assert result.status_code == 401
        assert len(responses.calls) == 1  # no refresh attempt at all

    @responses.activate
    def test_refresh_response_missing_access_token_raises(self):
        """A refresh response with no access_token field raises AuthenticationError."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(responses.POST, f"{AUTH_URL}/auth/refresh", json={}, status=200)

        with pytest.raises(AuthenticationError):
            s.request("GET", TARGET_URL)

    @responses.activate
    def test_refresh_rejected_by_server_raises_authentication_error(self):
        """omnibioai-auth's refresh tokens are single-use -- a reused or
        expired one is rejected with 401 by /auth/refresh itself."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            json={"detail": "Invalid refresh token"}, status=401,
        )

        with pytest.raises(AuthenticationError) as ctx:
            s.request("GET", TARGET_URL)
        assert ctx.value.status_code == 401

    @responses.activate
    def test_refresh_network_error_raises_authentication_error(self):
        """A connection error during the refresh call raises AuthenticationError."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            body=requests.exceptions.ConnectionError("network down"),
        )

        with pytest.raises(AuthenticationError):
            s.request("GET", TARGET_URL)

    @responses.activate
    def test_refresh_with_malformed_json_response_raises(self):
        """A non-JSON refresh response raises AuthenticationError."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            body="not json", status=200, content_type="text/plain",
        )

        with pytest.raises(AuthenticationError):
            s.request("GET", TARGET_URL)

    @responses.activate
    def test_refresh_without_new_refresh_token_keeps_old_one(self):
        """Some server responses might omit refresh_token (defensive
        case) -- the SDK must not clobber a still-valid held token with
        None."""
        s = _session()
        responses.add(responses.GET, TARGET_URL, json={"detail": "expired"}, status=401)
        responses.add(
            responses.POST, f"{AUTH_URL}/auth/refresh",
            json={"access_token": "access-2"}, status=200,
        )
        responses.add(responses.GET, TARGET_URL, json={"ok": True}, status=200)

        s.request("GET", TARGET_URL)

        assert s.tokens.refresh_token == "refresh-1"
