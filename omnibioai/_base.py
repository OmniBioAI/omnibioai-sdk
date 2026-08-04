"""omnibioai/_base.py"""
from __future__ import annotations

from typing import Any, Optional

import requests

from .auth.session import AuthenticatedSession
from .exceptions import (
    AuthenticationError,
    GatewayError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


class BaseServiceClient:
    """Shared request/response plumbing every service sub-client (rag,
    models, workflows, ...) is built on. Owns exactly one thing: turning
    a requests.Response into either parsed JSON or a typed
    OmniBioAIError. Auth/retry/trace-id mechanics live one layer below,
    in AuthenticatedSession (auth/session.py) -- this class never touches
    a token directly.
    """

    def __init__(self, base_url: str, session: AuthenticatedSession) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._session.request(method, self._url(path), **kwargs)
        return self._parse(response)

    def _parse(self, response: requests.Response) -> Any:
        body = _safe_json(response)
        trace_id = self._session.last_trace_id

        if response.status_code == 200:
            # API Gateway's specific unknown-service convention: HTTP 200
            # with a body that is *only* {"error": "..."} (see
            # exceptions.GatewayError's docstring) -- an observed, real
            # inconsistency, not a hypothetical one (Phase 1 findings).
            # Deliberately narrow (exact single-key shape) so a
            # legitimate 200 response that happens to carry an unrelated
            # "error" field among otherwise-real data is never
            # misclassified as this gateway-specific case.
            if isinstance(body, dict) and set(body.keys()) == {"error"}:
                raise GatewayError(
                    str(body["error"]),
                    status_code=200,
                    response_body=body,
                    trace_id=trace_id,
                )
            return body

        message = _extract_message(body) or response.reason or f"HTTP {response.status_code}"

        if response.status_code == 401:
            raise AuthenticationError(message, status_code=401, response_body=body, trace_id=trace_id)
        if response.status_code == 403:
            raise PermissionDeniedError(message, status_code=403, response_body=body, trace_id=trace_id)
        if response.status_code == 404:
            raise ResourceNotFoundError(message, status_code=404, response_body=body, trace_id=trace_id)
        if response.status_code >= 500:
            raise ServiceUnavailableError(message, status_code=response.status_code, response_body=body, trace_id=trace_id)
        if response.status_code >= 400:
            raise ValidationError(message, status_code=response.status_code, response_body=body, trace_id=trace_id)

        # Any other 2xx/3xx not already returned above (e.g. 201, 204).
        return body


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _extract_message(body: Any) -> Optional[str]:
    """Normalizes the ecosystem's several observed error-body shapes into
    one human-readable message string:
      - API Gateway:         {"error": "...", "reason": "..."}
      - FastAPI default:      {"detail": "..."}       (RAG, control-center, TES, most of Model Registry)
      - Model Registry (DB):  {"detail": {"ok": false, "error": "..."}}
    See the Phase 1 findings report's Cross-Service Consistency section
    for the full survey this is built from. Returns None (falls back to
    response.reason at the call site) if the body doesn't match any
    known shape."""
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        nested = detail.get("error") or detail.get("reason")
        if nested:
            return str(nested)
    error = body.get("error")
    if error:
        reason = body.get("reason")
        return f"{error}: {reason}" if reason else str(error)
    return None
