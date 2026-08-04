"""omnibioai/workflows/client.py"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .._base import BaseServiceClient
from ..exceptions import ResourceNotFoundError


class WorkflowsClient(BaseServiceClient):
    """Wraps omnibioai-workflow-bundles -- named, versioned, multi-tool
    pipeline execution -- as this SDK's high-level workflow interface:

        client.workflows.run("rna-seq-pipeline", inputs={...})

    Deliberately a separate abstraction from TESClient
    (omnibioai/tes/client.py), not merged into one client: this wraps a
    different backend service with a different resource model (named
    workflow bundles, not individual tool_id executions) -- see
    TESClient's own docstring for the full rationale.

    IMPORTANT INFRASTRUCTURE GAP, not an SDK design choice: unlike every
    other sub-client in this SDK, omnibioai-workflow-bundles has **no
    confirmed route in the API Gateway's SERVICE_MAP** (verified directly
    against that repo's app/core/router.py, both during Phase 1 discovery
    and again now -- still true). `workflows_url` therefore defaults to
    `{gateway_base_url}/workflow-bundles`, matching this ecosystem's own
    naming convention for when that gateway route is eventually added,
    but **must be overridden with a direct URL to workflow-bundles today**
    if the gateway doesn't proxy to it in a given deployment. See the SDK
    Phase 1 findings report, Open Question #3.

    Only transports whatever access token the shared AuthenticatedSession
    holds -- no JWT decoding, no permission checks, no IAM logic. Unlike
    RAG/TES/(most of) Model Registry, omnibioai-workflow-bundles enforces
    no IAM permission on any endpoint today (confirmed directly, both at
    Phase 1 discovery and again now) -- the token is still sent on every
    request regardless, same reasoning as the Model Registry client:
    costs nothing, and means no SDK change is needed once that closes.
    """

    def list(self) -> List[dict]:
        """GET /v1/workflows -- every registered workflow bundle (all
        categories, all versions)."""
        return self._request("GET", "/v1/workflows")

    def get(self, workflow_name: str) -> List[dict]:
        """GET /v1/workflows/{name} -- every registered version of
        `workflow_name`, newest first (the backend's own ordering).
        404s (-> ResourceNotFoundError) if no version of this name is
        registered at all."""
        return self._request("GET", f"/v1/workflows/{workflow_name}")

    def get_inputs(self, workflow_id: int) -> dict:
        """GET /v1/workflows/{workflow_id}/inputs -- default inputs,
        engine, entrypoint, and input schema for one specific
        (numeric-id-addressed) workflow version."""
        return self._request("GET", f"/v1/workflows/{workflow_id}/inputs")

    def run(
        self,
        workflow_name: str,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        engine: Optional[str] = None,
        version: Optional[str] = None,
    ) -> dict:
        """Resolves `workflow_name` (the newest registered version,
        unless `version` pins a specific one) to its numeric workflow_id
        via get(), then POSTs /v1/workflows/{id}/run -- composing two
        real backend endpoints, since omnibioai-workflow-bundles has no
        single "run by name" endpoint of its own. Raises
        ResourceNotFoundError if `workflow_name` doesn't exist at all
        (surfaced by get()'s own 404) or if `version` is given but no
        registered version matches it."""
        versions = self.get(workflow_name)

        if version is not None:
            matches = [v for v in versions if v.get("version") == version]
            if not matches:
                raise ResourceNotFoundError(
                    f"Workflow '{workflow_name}' has no version '{version}'"
                )
            target = matches[0]
        else:
            target = versions[0]

        payload: Dict[str, Any] = {}
        if inputs is not None:
            payload["inputs"] = inputs
        if engine is not None:
            payload["engine"] = engine

        return self._request("POST", f"/v1/workflows/{target['id']}/run", json=payload)

    def status(self, run_id: str) -> dict:
        """GET /v1/runs/{run_id} -- run status, recent log tail, and
        timing."""
        return self._request("GET", f"/v1/runs/{run_id}")
