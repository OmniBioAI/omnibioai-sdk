"""omnibioai/rag/client.py"""
from __future__ import annotations

from typing import Literal, Optional

from .._base import BaseServiceClient


class RAGClient(BaseServiceClient):
    """Wraps omnibioai-rag's knowledge-retrieval endpoints, reached
    through the API Gateway at `{gateway_base_url}/rag/...` -- this
    client never talks to RAG directly, per the SDK's own documented
    "always go through the gateway" guidance.

    All four methods here require the `dataset.read` IAM permission on
    the token this client's session holds (enforced server-side, in RAG
    itself -- see omnibioai-rag's ragbio/api/iam.py). This client does
    not pre-check that permission client-side; a token lacking it
    surfaces as PermissionDeniedError from the normal request/response
    path, same as any other permission failure (see the Phase 1 findings
    report's Permission Awareness section for why: the server is the
    single source of truth for what a token can do, not a client-side
    copy of that mapping).

    RAG's other endpoints (/v1/ingest, /v1/embed, /v1/studies, /v1/cache*,
    /v1/kg/build, /v1/benchmark) are pipeline/ops operations gated by a
    separate flat API key, not IAM -- deliberately not wrapped here; see
    the Phase 1 findings report.
    """

    def query(
        self,
        query: str,
        *,
        study: str = "default",
        top_k: Optional[int] = None,
        mode: Literal["rag", "pmids_only", "structured"] = "rag",
        hybrid_search: bool = False,
    ) -> dict:
        """POST /v1/query. `top_k` is omitted from the request entirely
        when not given, rather than the SDK hardcoding a default that
        could drift from RAG's own server-side default (ragbio.config.TOP_K)."""
        payload: dict = {
            "query": query,
            "study": study,
            "mode": mode,
            "hybrid_search": hybrid_search,
        }
        if top_k is not None:
            payload["top_k"] = top_k
        return self._request("POST", "/v1/query", json=payload)

    def kg_stats(self) -> dict:
        """GET /v1/kg/stats -- knowledge graph node counts."""
        return self._request("GET", "/v1/kg/stats")

    def kg_entity(self, name: str, type: Optional[str] = None) -> dict:
        """GET /v1/kg/entity -- an entity and its relationships."""
        params = {"name": name}
        if type is not None:
            params["type"] = type
        return self._request("GET", "/v1/kg/entity", params=params)

    def kg_drug_disease(self, disease: str) -> dict:
        """GET /v1/kg/drug-disease -- drugs associated with a disease via
        shared papers."""
        return self._request("GET", "/v1/kg/drug-disease", params={"disease": disease})
