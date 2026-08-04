"""
tests/test_exceptions.py

Unit tests for omnibioai/exceptions.py and the error-normalization logic
in omnibioai/_base.py::BaseServiceClient._parse -- one test per (status
code, response-body shape) pair identified in the Phase 1 findings
report's Cross-Service Consistency section.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from omnibioai._base import BaseServiceClient, _extract_message
from omnibioai.exceptions import (
    AuthenticationError,
    GatewayError,
    OmniBioAIError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)


def _response(status_code, json_body=None, reason="Error"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.reason = reason
    if json_body is None:
        resp.json.side_effect = ValueError("no body")
    else:
        resp.json.return_value = json_body
    return resp


def _client():
    session = MagicMock()
    session.last_trace_id = "trace-123"
    return BaseServiceClient(base_url="http://x", session=session)


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_omnibioai_error(self):
        for exc_cls in (
            AuthenticationError, PermissionDeniedError, ResourceNotFoundError,
            ValidationError, ServiceUnavailableError, GatewayError,
        ):
            assert issubclass(exc_cls, OmniBioAIError)

    def test_carries_status_code_body_and_trace_id(self):
        exc = AuthenticationError("bad token", status_code=401, response_body={"a": 1}, trace_id="t1")
        assert exc.status_code == 401
        assert exc.response_body == {"a": 1}
        assert exc.trace_id == "t1"
        assert str(exc) == "bad token"


class TestStatusCodeMapping:
    """Gateway ({"error":..., "reason":...}), FastAPI-default
    ({"detail": "..."}), and Model Registry's nested
    ({"detail": {"ok": false, "error": ...}}) shapes are all exercised
    here, per the Phase 1 findings survey."""

    def test_401_fastapi_default_shape_raises_authentication_error(self):
        c = _client()
        with pytest.raises(AuthenticationError) as ctx:
            c._parse(_response(401, {"detail": "Invalid, expired, or revoked token"}))
        assert "Invalid, expired, or revoked token" in str(ctx.value)
        assert ctx.value.status_code == 401
        assert ctx.value.trace_id == "trace-123"

    def test_403_gateway_shape_raises_permission_denied_error(self):
        c = _client()
        with pytest.raises(PermissionDeniedError) as ctx:
            c._parse(_response(403, {"error": "forbidden", "reason": "no_permission"}))
        assert "forbidden" in str(ctx.value)
        assert "no_permission" in str(ctx.value)

    def test_403_tes_named_permission_message_preserved(self):
        c = _client()
        with pytest.raises(PermissionDeniedError) as ctx:
            c._parse(_response(403, {"detail": "missing permission: workflow.execute"}))
        assert "workflow.execute" in str(ctx.value)

    def test_404_raises_resource_not_found_error(self):
        c = _client()
        with pytest.raises(ResourceNotFoundError):
            c._parse(_response(404, {"detail": "Run abc not found"}))

    def test_422_raises_validation_error(self):
        c = _client()
        with pytest.raises(ValidationError):
            c._parse(_response(422, {"detail": "invalid field"}))

    def test_500_raises_service_unavailable_error(self):
        c = _client()
        with pytest.raises(ServiceUnavailableError):
            c._parse(_response(500, {"detail": "internal error"}))

    def test_503_raises_service_unavailable_error(self):
        c = _client()
        with pytest.raises(ServiceUnavailableError):
            c._parse(_response(503, {"detail": "database unavailable"}))

    def test_model_registry_nested_detail_shape_message_extracted(self):
        c = _client()
        with pytest.raises(ServiceUnavailableError) as ctx:
            c._parse(_response(503, {"detail": {"ok": False, "error": "database module not available"}}))
        assert "database module not available" in str(ctx.value)

    def test_no_body_falls_back_to_reason(self):
        c = _client()
        with pytest.raises(ServiceUnavailableError) as ctx:
            c._parse(_response(500, json_body=None, reason="Internal Server Error"))
        assert "Internal Server Error" in str(ctx.value)

    def test_201_created_returned_as_is(self):
        c = _client()
        body = {"ok": True, "job_id": "abc"}
        assert c._parse(_response(201, body)) == body


class TestGatewayUnknownServiceCase:
    """The API Gateway's catch-all proxy returns HTTP 200 with
    {"error": "unknown service"} for an unresolvable service segment --
    not a 404. Must be raised as GatewayError, not returned as success."""

    def test_200_with_only_error_key_raises_gateway_error(self):
        c = _client()
        with pytest.raises(GatewayError) as ctx:
            c._parse(_response(200, {"error": "unknown service"}))
        assert "unknown service" in str(ctx.value)
        assert ctx.value.status_code == 200

    def test_200_with_error_key_among_real_data_is_not_misclassified(self):
        """A legitimate 200 response that happens to carry an "error"
        field alongside real data (not the gateway's exact single-key
        shape) must be returned as-is, not raised."""
        c = _client()
        body = {"error": None, "results": [1, 2, 3]}
        result = c._parse(_response(200, body))
        assert result == body

    def test_normal_200_response_returned_as_is(self):
        c = _client()
        body = {"ok": True, "data": {"x": 1}}
        assert c._parse(_response(200, body)) == body


class TestExtractMessage:
    def test_none_for_non_dict_body(self):
        assert _extract_message("not a dict") is None
        assert _extract_message(None) is None

    def test_none_for_dict_with_no_known_keys(self):
        assert _extract_message({"unrelated": "field"}) is None

    def test_none_when_nested_detail_dict_has_no_error_or_reason(self):
        assert _extract_message({"detail": {"ok": False}}) is None
