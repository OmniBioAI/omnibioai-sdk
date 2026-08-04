"""
omnibioai/legacy.py

The original OmniBioAI SDK client, moved here unchanged from
omnibioai_sdk/client.py as part of the omnibioai_sdk -> omnibioai package
migration (SDK Phase 2). This is a pure relocation, not a rewrite -- every
line of behavior is identical to the pre-migration OmniClient.

Wraps the object-registry dev API (GET /api/dev/objects/, GET
/api/dev/objects/{id}/) -- an unrelated surface from the RAG/models/
workflows clients living alongside it in this package. Kept under its own
module (not folded into client.py or given IAM-aware error handling) so
existing callers see zero behavior change: no shared Session, no trace ID
injection, no OmniBioAIError normalization -- exactly what
tests/test_client.py already asserts.

omnibioai_sdk/client.py and omnibioai_sdk/__init__.py now just re-export
OmniClient from here, so `from omnibioai_sdk import OmniClient` (every
existing caller's import path) keeps working, unchanged, indefinitely.
`from omnibioai import OmniClient` also works, for callers migrating to
the new package namespace who still need this client.
"""
import os
import requests


class OmniClient:
    """
    Minimal Python client for the OmniBioAI object registry API.
    """

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: int = 60):
        self.base_url = (base_url or os.getenv("OMNIBIOAI_BASE_URL", "http://127.0.0.1:8001")).rstrip("/")
        self.token = token or os.getenv("OMNIBIOAI_TOKEN", "dev")
        self.timeout = timeout

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def objects_list(self) -> dict:
        r = requests.get(f"{self.base_url}/api/dev/objects/", headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def object_get(self, object_id: str) -> dict:
        r = requests.get(f"{self.base_url}/api/dev/objects/{object_id}/", headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        return r.json()
