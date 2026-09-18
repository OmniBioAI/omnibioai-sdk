"""
tests/test_tes_client.py

Unit tests for omnibioai/tes/client.py::TESClient -- request-shape
correctness against omnibioai-tes's actual /api/runs/* contract, the
standard error-mapping outcomes (authentication failure, permission
denied, service unavailable), and a full successful submit -> status ->
logs -> results -> cancel lifecycle.

Developer:
    Manish Kumar <manish@omnibioai.org>
"""
from __future__ import annotations

import json

import responses

from omnibioai import OmniBioAI
from omnibioai.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    ServiceUnavailableError,
)

BASE = "https://gateway.example.com"
RUN_ID = "run_abc123"


def _client():
    """An OmniBioAI client pointed at the module's mock gateway BASE."""
    return OmniBioAI(access_token="tok", base_url=BASE)


class TestSubmit:
    """TESClient.submit() request-shape and default handling, and TES's own {ok: false,
    error: ...} business-logic failure returned as a normal 200 rather than raised."""
    @responses.activate
    def test_minimal_call_sends_expected_payload(self):
        """A minimal submit() call sends empty inputs/resources/constraints and returns
        the run_id."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/submit",
            json={"ok": True, "run_id": RUN_ID, "server_id": "srv1", "remote_run_id": None},
            status=200,
        )
        result = c.tes.submit("echo_test")

        assert result["ok"] is True
        assert result["run_id"] == RUN_ID
        sent = json.loads(responses.calls[0].request.body)
        assert sent == {"tool_id": "echo_test", "inputs": {}, "resources": {}, "constraints": {}}

    @responses.activate
    def test_all_params_forwarded(self):
        """inputs, resources and constraints are forwarded exactly as given, and
        server_id is sent as a query parameter."""
        c = _client()
        responses.add(responses.POST, f"{BASE}/tes/api/runs/submit", json={"ok": True}, status=200)
        c.tes.submit(
            "blast", inputs={"query": "ATCG"}, resources={"cpus": 4},
            constraints={"preferred_server_id": "srv2"}, server_id="srv2",
        )
        sent = json.loads(responses.calls[0].request.body)
        assert sent == {
            "tool_id": "blast", "inputs": {"query": "ATCG"}, "resources": {"cpus": 4},
            "constraints": {"preferred_server_id": "srv2"},
        }
        assert "server_id=srv2" in responses.calls[0].request.url

    @responses.activate
    def test_uses_gateway_tes_prefix(self):
        """submit() posts to the gateway's /tes/api/runs/submit path."""
        c = _client()
        responses.add(responses.POST, f"{BASE}/tes/api/runs/submit", json={"ok": True}, status=200)
        c.tes.submit("echo_test")
        assert responses.calls[0].request.url == f"{BASE}/tes/api/runs/submit"

    @responses.activate
    def test_business_logic_failure_returned_not_raised(self):
        """TES returns {"ok": False, "error": {...}} as a normal 200 for
        e.g. validation failures -- this is not an HTTP error and must
        not be raised as one."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/submit",
            json={"ok": False, "error": {"code": "VALIDATION_FAILED", "details": {}}},
            status=200,
        )
        result = c.tes.submit("bad_tool")
        assert result["ok"] is False
        assert result["error"]["code"] == "VALIDATION_FAILED"


class TestValidate:
    """TESClient.validate() calls POST /tes/api/runs/validate with the tool id and
    inputs."""
    @responses.activate
    def test_calls_validate_endpoint(self):
        """validate() sends tool_id and inputs and returns the validation result."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/validate",
            json={"ok": True, "errors": [], "warnings": [], "selected_server_id": "srv1", "per_server": {}},
            status=200,
        )
        result = c.tes.validate("echo_test", inputs={"text": "hi"})
        assert result["ok"] is True
        sent = json.loads(responses.calls[0].request.body)
        assert sent["tool_id"] == "echo_test"
        assert sent["inputs"] == {"text": "hi"}


class TestStatusLogsResults:
    """TESClient.status()/logs()/results(): polling a run's state, fetching its logs
    with a default or custom tail, and fetching results including the not-ready case."""
    @responses.activate
    def test_status_calls_expected_endpoint(self):
        """status(run_id) returns the run's current state."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}",
            json={"run_id": RUN_ID, "state": "RUNNING"}, status=200,
        )
        result = c.tes.status(RUN_ID)
        assert result["state"] == "RUNNING"

    @responses.activate
    def test_logs_default_tail(self):
        """logs(run_id) defaults to tail=200."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/logs",
            json={"run_id": RUN_ID, "logs": ["line1", "line2"]}, status=200,
        )
        result = c.tes.logs(RUN_ID)
        assert result["logs"] == ["line1", "line2"]
        assert "tail=200" in responses.calls[0].request.url

    @responses.activate
    def test_logs_custom_tail(self):
        """logs(run_id, tail=...) sends the given tail value."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/logs",
            json={"run_id": RUN_ID, "logs": []}, status=200,
        )
        c.tes.logs(RUN_ID, tail=50)
        assert "tail=50" in responses.calls[0].request.url

    @responses.activate
    def test_results_success(self):
        """results(run_id) returns the run's output data."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/results",
            json={"ok": True, "run_id": RUN_ID, "results": {"output": "s3://..."}}, status=200,
        )
        result = c.tes.results(RUN_ID)
        assert result["results"]["output"] == "s3://..."

    @responses.activate
    def test_results_not_ready_returned_not_raised(self):
        """A results response with ok=false and code NOT_READY is returned as-is, not
        raised."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/results",
            json={"ok": False, "error": {"code": "NOT_READY", "message": "state=RUNNING"}}, status=200,
        )
        result = c.tes.results(RUN_ID)
        assert result["ok"] is False


class TestCancel:
    """TESClient.cancel() calls POST /tes/api/runs/{run_id}/cancel."""
    @responses.activate
    def test_calls_cancel_endpoint(self):
        """cancel(run_id) returns the run's CANCELLED state."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/{RUN_ID}/cancel",
            json={"ok": True, "run_id": RUN_ID, "state": "CANCELLED"}, status=200,
        )
        result = c.tes.cancel(RUN_ID)
        assert result["state"] == "CANCELLED"


class TestErrorMapping:
    """TESClient's standard error mapping: 401 to AuthenticationError, 403 to
    PermissionDeniedError (preserving the named permission), and 503 to
    ServiceUnavailableError."""
    @responses.activate
    def test_authentication_failure(self):
        """A 401 on submit() raises AuthenticationError with status_code 401."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/submit",
            json={"detail": "invalid token"}, status=401,
        )
        try:
            c.tes.submit("echo_test")
            assert False, "expected AuthenticationError"
        except AuthenticationError as exc:
            assert exc.status_code == 401

    @responses.activate
    def test_permission_denied(self):
        """A 403 on submit() naming a missing permission raises PermissionDeniedError
        whose message includes that permission."""
        c = _client()
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/submit",
            json={"detail": "missing permission: workflow.execute"}, status=403,
        )
        try:
            c.tes.submit("echo_test")
            assert False, "expected PermissionDeniedError"
        except PermissionDeniedError as exc:
            assert "workflow.execute" in str(exc)

    @responses.activate
    def test_service_unavailable(self):
        """A 503 on status() raises ServiceUnavailableError."""
        c = _client()
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}",
            json={"detail": "internal error"}, status=503,
        )
        try:
            c.tes.status(RUN_ID)
            assert False, "expected ServiceUnavailableError"
        except ServiceUnavailableError:
            pass


class TestFullLifecycle:
    """Submit, poll status, fetch logs, fetch results, then cancel, exercising all six
    required TES operations in one sequence."""
    @responses.activate
    def test_submit_status_logs_results_cancel(self):
        """End-to-end: submit a run, poll status, fetch logs, fetch
        results, then cancel -- exercising all six required TES
        operations in one realistic sequence."""
        c = _client()

        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/validate",
            json={"ok": True, "errors": [], "warnings": [], "selected_server_id": "srv1", "per_server": {}},
            status=200,
        )
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/submit",
            json={"ok": True, "run_id": RUN_ID, "server_id": "srv1", "remote_run_id": None}, status=200,
        )
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}",
            json={"run_id": RUN_ID, "state": "COMPLETED"}, status=200,
        )
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/logs",
            json={"run_id": RUN_ID, "logs": ["done"]}, status=200,
        )
        responses.add(
            responses.GET, f"{BASE}/tes/api/runs/{RUN_ID}/results",
            json={"ok": True, "run_id": RUN_ID, "results": {"output_file": "out.txt"}}, status=200,
        )
        responses.add(
            responses.POST, f"{BASE}/tes/api/runs/{RUN_ID}/cancel",
            json={"ok": True, "run_id": RUN_ID, "state": "CANCELLED"}, status=200,
        )

        validation = c.tes.validate("echo_test", inputs={"text": "hi"})
        assert validation["ok"] is True

        submitted = c.tes.submit("echo_test", inputs={"text": "hi"})
        run_id = submitted["run_id"]
        assert run_id == RUN_ID

        status = c.tes.status(run_id)
        assert status["state"] == "COMPLETED"

        logs = c.tes.logs(run_id)
        assert logs["logs"] == ["done"]

        results = c.tes.results(run_id)
        assert results["results"]["output_file"] == "out.txt"

        cancelled = c.tes.cancel(run_id)
        assert cancelled["state"] == "CANCELLED"

        assert len(responses.calls) == 6
        # Every call must carry the bearer token.
        for call in responses.calls:
            assert call.request.headers["Authorization"] == "Bearer tok"
