"""omnibioai/literature/client.py"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from .._base import BaseServiceClient


class LiteratureClient(BaseServiceClient):
    """The public, billable Literature AI API at `{gateway}/v1/literature`.

    Unlike `.rag` (the internal service route), this is the stable,
    versioned contract meant for API-key users: it is rate-limited per key
    (RateLimitError on 429), billed per answer (QuotaExceededError on 402
    once an organization's included answers run out), and every `ask()`
    sends an Idempotency-Key, so a retried call is answered from the
    gateway's stored result and never billed twice.

    Request fields are omnibioai-rag's POST /v1/query contract, passed
    through unchanged by the gateway.
    """

    def ask(
        self,
        question: str,
        *,
        study: str = "default",
        top_k: Optional[int] = None,
        mode: Literal["rag", "pmids_only", "structured"] = "rag",
        hybrid_search: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        """Ask a biomedical question; returns the answer with its PubMed
        citations. Pass the same `idempotency_key` when retrying a call
        whose outcome you did not see (one is generated otherwise). `top_k`
        is omitted unless given, so the server's own default applies."""
        payload: dict = {
            "query": question,
            "study": study,
            "mode": mode,
            "hybrid_search": hybrid_search,
        }
        if top_k is not None:
            payload["top_k"] = top_k
        headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4())}
        return self._request("POST", "/answers", json=payload, headers=headers)

    def studies(self) -> dict:
        """The queryable studies/research domains. Free, still rate-limited."""
        return self._request("GET", "/studies")
