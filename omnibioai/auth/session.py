"""omnibioai/auth/session.py"""
from __future__ import annotations

import uuid
from typing import Any, Optional

import requests

from ..exceptions import AuthenticationError
from .tokens import TokenPair

REFRESH_PATH = "/auth/refresh"


class AuthenticatedSession:
    """Wraps one shared requests.Session for every OmniBioAI sub-client.
    Owns exactly two cross-cutting concerns every request needs, so no
    individual service client (rag/models/workflows) has to re-implement
    either:

      1. Auth: injects the current access token's Authorization header,
         and -- on a 401 -- attempts exactly one token refresh (via
         auth_url + /auth/refresh) before retrying the original request
         once with the new access token. A second 401 (or a refresh
         failure) raises AuthenticationError rather than retrying again;
         this mirrors omnibioai-auth's own refresh-token contract, where
         a *second* presentation of an already-rotated refresh token is
         treated as token-family compromise, not a retriable failure.

      2. Trace propagation: an X-Trace-Id header, generated fresh per
         call unless the caller supplies one, matching the header name
         every IAM Foundation service (gateway, RAG, TES, ...) already
         reads. Recorded on `last_trace_id` after every call so a raised
         OmniBioAIError can carry it for cross-service debugging.

    Deliberately does NOT decode/verify the JWT it holds, and does not
    import omnibioai-iam-client -- see the Phase 1 findings report,
    Authentication Design section, for why that boundary is intentional:
    IAM verification is the API Gateway's and each service's
    responsibility, not this SDK's.
    """

    def __init__(
        self,
        tokens: TokenPair,
        auth_url: str,
        timeout: float = 60,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.tokens = tokens
        self.auth_url = auth_url.rstrip("/")
        self.timeout = timeout
        self._http = session or requests.Session()
        self.last_trace_id: Optional[str] = None

    def request(
        self,
        method: str,
        url: str,
        *,
        trace_id: Optional[str] = None,
        _is_retry: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        trace_id = trace_id or str(uuid.uuid4())
        self.last_trace_id = trace_id

        headers = dict(kwargs.pop("headers", None) or {})
        headers.update(self.tokens.auth_header())
        headers["X-Trace-Id"] = trace_id

        response = self._http.request(
            method, url, headers=headers, timeout=self.timeout, **kwargs
        )

        if response.status_code == 401 and not _is_retry and self.tokens.refresh_token:
            self._refresh()
            return self.request(method, url, trace_id=trace_id, _is_retry=True, **kwargs)

        return response

    def _refresh(self) -> None:
        """Rotates the held refresh token via POST {auth_url}/auth/refresh.
        Always raises AuthenticationError (never returns/falls through
        silently) if the call fails outright or the refresh token itself
        is rejected -- omnibioai-auth's refresh tokens are single-use, so
        there is no safe retry here beyond the one request() already
        gives via its _is_retry guard."""
        try:
            resp = self._http.post(
                f"{self.auth_url}{REFRESH_PATH}",
                json={"refresh_token": self.tokens.refresh_token},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AuthenticationError(
                f"Token refresh failed: {exc}", trace_id=self.last_trace_id,
            ) from exc

        if resp.status_code != 200:
            raise AuthenticationError(
                "Token refresh failed: refresh token is invalid, expired, or already used",
                status_code=resp.status_code,
                response_body=_safe_json(resp),
                trace_id=self.last_trace_id,
            )

        data = _safe_json(resp) or {}
        access_token = data.get("access_token")
        if not access_token:
            raise AuthenticationError(
                "Token refresh response did not include an access_token",
                status_code=resp.status_code,
                response_body=data,
                trace_id=self.last_trace_id,
            )

        self.tokens.access_token = access_token
        # omnibioai-auth's refresh tokens are single-use (rotated on every
        # call) -- always adopt the new one when present so a *future*
        # refresh doesn't replay an already-exchanged token, which
        # omnibioai-auth treats as token-family compromise and revokes
        # every descendant of that login.
        new_refresh = data.get("refresh_token")
        if new_refresh:
            self.tokens.refresh_token = new_refresh


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
