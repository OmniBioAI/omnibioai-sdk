import os
import requests


class OmniClient:
    """
    Minimal dev client for OmniBioAI object registry API.
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

    def get_launch_urls(self, object_id: str) -> dict:
        """Returns all launch URLs for a given object."""
        jupyter_base = os.getenv("OMNIBIOAI_JUPYTER_BASE", "http://127.0.0.1:8890")
        jupyter_token = os.getenv("OMNIBIOAI_JUPYTER_TOKEN", "devtoken")
        return {
            "notebook": f"{jupyter_base}/lab?token={jupyter_token}&omnibioai_object_id={object_id}",
            "vscode": "vscode://",
            "rstudio": "rstudio://",
        }

    def get_launcher_url(self, object_id: str, launcher_port: int = 5190) -> str:
        """Returns the launcher UI URL for a given object."""
        return f"http://127.0.0.1:{launcher_port}/?object_id={object_id}"

    def generate_r_script(self, object_id: str) -> str:
        """Generates a ready-to-run R script for the given object."""
        obj = self.object_get(object_id)
        name = obj.get("name", "Unknown")
        object_type = obj.get("object_type", "Unknown")
        return f"""# OmniBioAI — auto-generated starter script
# Object: {name}
# Type:   {object_type}
# ID:     {object_id}

Sys.setenv(
  OMNIBIOAI_OBJECT_ID = "{object_id}",
  OMNIBIOAI_BASE_URL  = "{self.base_url}",
  OMNIBIOAI_TOKEN     = "{self.token}"
)

library(httr2)

client <- list(
  base_url = Sys.getenv("OMNIBIOAI_BASE_URL"),
  token    = Sys.getenv("OMNIBIOAI_TOKEN")
)

obj <- request(client$base_url) |>
  req_url_path(paste0("/api/dev/objects/", Sys.getenv("OMNIBIOAI_OBJECT_ID"), "/")) |>
  req_headers(Authorization = paste("Bearer", client$token)) |>
  req_perform() |>
  resp_body_json()

cat("Loaded:", obj$object_type, "\\n")
print(obj$metadata)
"""

    def generate_python_snippet(self, object_id: str) -> str:
        """Generates env var export block for Python/VS Code usage."""
        return f"""export OMNIBIOAI_OBJECT_ID="{object_id}"
export OMNIBIOAI_BASE_URL="{self.base_url}"
export OMNIBIOAI_TOKEN="{self.token}"

# Then in your script:
from omnibioai_sdk import OmniClient
import os

c = OmniClient()
obj = c.object_get(os.environ["OMNIBIOAI_OBJECT_ID"])
print(obj["object_type"], obj["metadata"])
"""
