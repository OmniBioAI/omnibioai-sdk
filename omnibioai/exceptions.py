"""
omnibioai/exceptions.py

The SDK-wide exception hierarchy every service client (rag, models,
workflows, ...) normalizes HTTP responses into. See omnibioai/_base.py for
the normalization logic itself.

Deliberately keyed off HTTP status code, not response body shape: the
services behind this SDK disagree on error body shape (the API Gateway's
own {"error": ..., "reason": ...} vs. the FastAPI-default {"detail": "..."}
every other integrated service uses vs. Model Registry's one nested
{"detail": {"ok": false, "error": ...}} path) -- see the Phase 1 findings
report for the full cross-service survey. Callers should catch by
exception type, never by inspecting response body keys directly.
"""
from __future__ import annotations

from typing import Any, Optional


class OmniBioAIError(Exception):
    """Base class for every exception this SDK raises from a service
    response. `status_code` is None for errors raised before any response
    was received (e.g. a failed token refresh) or a request layer wraps a
    non-HTTP error, present otherwise. `response_body` is whatever the
    service returned (parsed JSON if possible, else the raw text) -- kept
    for debugging, never required by SDK-internal logic. `trace_id` is
    the X-Trace-Id this SDK sent (or received back) for the request that
    raised, when known -- correlate this with a service's own audit
    trail when reporting an issue."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Any = None,
        trace_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.trace_id = trace_id


class AuthenticationError(OmniBioAIError):
    """401: missing, invalid, expired, or revoked access token -- or a
    token-refresh attempt itself failed (invalid/expired/reused refresh
    token), in which case status_code reflects the /auth/refresh call's
    own response, not the original request's."""


class PermissionDeniedError(OmniBioAIError):
    """403: the token was valid but lacks a required IAM permission.
    Where a service names the missing permission in its response (most
    do, e.g. omnibioai-tes's "missing permission: workflow.execute"),
    that text is preserved in the exception message verbatim."""


class ResourceNotFoundError(OmniBioAIError):
    """404."""


class ValidationError(OmniBioAIError):
    """Any other 4xx (400, 422, ...) -- malformed request, not an auth
    failure."""


class ServiceUnavailableError(OmniBioAIError):
    """5xx from a downstream service, or the API Gateway's own upstream-
    proxy failure response."""


class GatewayError(OmniBioAIError):
    """The API Gateway's specific 200-status-but-actually-an-error
    convention: an unresolvable {service} path segment in its catch-all
    proxy route responds HTTP 200 with body {"error": "unknown service"}
    -- a real, observed inconsistency (see Phase 1 findings), not a
    hypothetical one. status_code is always 200 for this exception;
    distinguishing it from ServiceUnavailableError/ValidationError lets a
    caller tell "the gateway itself doesn't know this route" apart from
    "the target service rejected the request"."""
