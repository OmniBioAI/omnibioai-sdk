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
