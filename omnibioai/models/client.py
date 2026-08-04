"""omnibioai/models/client.py"""
from __future__ import annotations

from typing import Optional

from .._base import BaseServiceClient


class ModelsClient(BaseServiceClient):
    """Wraps omnibioai-model-registry's read endpoints, reached through
    the API Gateway at `{gateway_base_url}/model-registry/...`.

    IMPORTANT DEVIATION FROM THE TARGET EXAMPLE: the target architecture's
    `client.models.get("esm2")` implies a model is addressable by a bare
    name alone. It isn't -- omnibioai-model-registry's actual data model
    is task-scoped (task/model_name/version, or task/model_name/alias),
    with no endpoint that looks up a model by name across all tasks. This
    client's methods require `task` explicitly rather than inventing a
    cross-task name search the backend doesn't support -- see the Phase 1
    findings report and this PR's description for the full rationale.

    ALWAYS sends the current access token, on every method, even though
    Phase 1 discovery confirmed several of these read endpoints
    (`/resolve`, `/show`, `/models`) enforce no IAM permission at all
    today (and `AUTH_ENABLED` defaults to False service-side regardless).
    This is deliberate, per explicit instruction: closing that
    server-side gap is out of scope for this SDK PR. Sending the token
    anyway costs nothing and means no SDK-side change is needed the day
    that gap closes.
    """

    def get(self, task: str, ref: str, *, verify: bool = False) -> dict:
        """GET /v1/show -- resolves `ref` (a version string or an alias
        like "latest") within `task` and returns its metadata
        (model_meta.json) alongside the resolved package directory."""
        return self._request(
            "GET", "/v1/show", params={"task": task, "ref": ref, "verify": verify},
        )

    def resolve(self, task: str, ref: str, *, verify: bool = True) -> dict:
        """GET /v1/resolve -- resolves `ref` within `task` to a filesystem
        path, optionally verifying its integrity manifest. Lower-level
        than get(): most callers want get() for metadata instead."""
        return self._request(
            "GET", "/v1/resolve", params={"task": task, "ref": ref, "verify": verify},
        )

    def list(
        self,
        *,
        task: Optional[str] = None,
        model_name: Optional[str] = None,
        metric_gte: Optional[str] = None,
    ) -> dict:
        """GET /v1/models -- lists registered models, optionally filtered
        by task, model_name, and/or a "key:threshold" metric filter
        (matching the backend's own filter semantics exactly)."""
        params = {
            k: v for k, v in
            {"task": task, "model_name": model_name, "metric_gte": metric_gte}.items()
            if v is not None
        }
        return self._request("GET", "/v1/models", params=params)
