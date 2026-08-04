"""omnibioai/tes/client.py"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .._base import BaseServiceClient


class TESClient(BaseServiceClient):
    """Wraps omnibioai-tes -- the low-level tool/job execution engine --
    reached through the API Gateway at `{gateway_base_url}/tes/api/...`
    (SERVICE_MAP already maps "tes" -> workflow.execute; unlike
    omnibioai-workflow-bundles, no separate URL override is needed here).

    Deliberately a separate abstraction from WorkflowsClient
    (omnibioai/workflows/client.py), not merged into one client: TES
    submits/tracks individual tool executions by tool_id, while
    omnibioai-workflow-bundles runs named, versioned, multi-tool
    pipelines. They are different resources with different identifiers
    (tool_id vs. workflow_name) and different lifecycles -- collapsing
    them into one client would blur that distinction, not simplify it.

    This client, like every other one in this SDK, only transports
    whatever access token the shared AuthenticatedSession holds -- no
    JWT decoding, no permission checks, no IAM logic of any kind. Every
    method here requires the `workflow.execute` IAM permission
    server-side (enforced by omnibioai-tes itself); a token lacking it
    surfaces as PermissionDeniedError through the normal response path.
    """

    def submit(
        self,
        tool_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        *,
        server_id: Optional[str] = None,
    ) -> dict:
        """POST /api/runs/submit. Returns
        {"ok": True, "run_id", "server_id", "remote_run_id"} on success,
        or {"ok": False, "error": {...}} for a business-logic failure
        (e.g. validation failed, server not found) -- that shape is
        TES's own, returned as a normal 200; this client does not
        reinterpret it as an exception, since it isn't an HTTP error."""
        return self._request(
            "POST", "/api/runs/submit",
            json=self._run_request(tool_id, inputs, resources, constraints),
            params={"server_id": server_id} if server_id else None,
        )

    def validate(
        self,
        tool_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        *,
        server_id: Optional[str] = None,
    ) -> dict:
        """POST /api/runs/validate -- dry-run validation, same request
        shape as submit() but never actually executes anything. Returns
        a ValidationReport-shaped dict:
        {"ok", "errors", "warnings", "selected_server_id", "per_server"}."""
        return self._request(
            "POST", "/api/runs/validate",
            json=self._run_request(tool_id, inputs, resources, constraints),
            params={"server_id": server_id} if server_id else None,
        )

    def status(self, run_id: str) -> dict:
        """GET /api/runs/{run_id} -- the full RunRecord (state,
        exit_code, error, results, ...)."""
        return self._request("GET", f"/api/runs/{run_id}")

    def logs(self, run_id: str, *, tail: int = 200) -> dict:
        """GET /api/runs/{run_id}/logs -- {"run_id", "logs": [...]}."""
        return self._request("GET", f"/api/runs/{run_id}/logs", params={"tail": tail})

    def results(self, run_id: str) -> dict:
        """GET /api/runs/{run_id}/results. {"ok": False, "error": {"code": "NOT_READY", ...}}
        (a normal 200, not an exception) if the run hasn't reached
        COMPLETED state yet."""
        return self._request("GET", f"/api/runs/{run_id}/results")

    def cancel(self, run_id: str) -> dict:
        """POST /api/runs/{run_id}/cancel -- marks the run CANCELLED.
        Does not attempt adapter-level remote cancellation (most
        adapters don't support it) -- matches omnibioai-tes's own
        documented scope for this endpoint."""
        return self._request("POST", f"/api/runs/{run_id}/cancel")

    @staticmethod
    def _run_request(
        tool_id: str,
        inputs: Optional[Dict[str, Any]],
        resources: Optional[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]],
    ) -> dict:
        return {
            "tool_id": tool_id,
            "inputs": inputs or {},
            "resources": resources or {},
            "constraints": constraints or {},
        }
