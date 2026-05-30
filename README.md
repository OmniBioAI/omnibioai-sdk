# OmniBioAI SDK

**OmniBioAI SDK** is a lightweight Python client for interacting with the **OmniBioAI platform APIs**, including:

* Object Registry (datasets, studies, jobs, workflows)
* Development APIs (`/api/dev/*`)
* Jupyter-based interactive analysis workflows

The SDK is intentionally **thin and explicit** — it does not hide API behavior and is designed to evolve alongside the OmniBioAI platform.

---

## Features

* Simple Python client (`OmniClient`)
* Works with local OmniBioAI development servers
* No Docker required
* Designed for notebooks, scripts, and pipelines
* Explicit auth and base URL control
* Easy to extend with new API endpoints

---

## Installation

```bash
pip install omnibioai-sdk
```

Or during development:

```bash
pip install -e .
```

---

## Quick Start

```python
from omnibioai_sdk import OmniClient

c = OmniClient(
    base_url="http://127.0.0.1:8001",
    token="dev"
)

objects = c.objects_list()
print(objects["count"])
```

---

## Authentication

The SDK uses **header-based authentication**.

For development:

```text
Authorization: Bearer dev
```

You can pass credentials explicitly or via environment variables.

### Environment Variables (recommended)

```bash
export OMNIBIOAI_BASE_URL=http://127.0.0.1:8001
export OMNIBIOAI_TOKEN=dev
```

Then simply:

```python
c = OmniClient()
```

---

## Object Registry API

### List objects

```python
lst = c.objects_list()
lst["count"]
lst["items"][0]
```

### Get a single object

```python
obj = c.object_get("56d3fc3a-709b-4ed0-bf17-8cb73c6746b0")
print(obj["object_type"])
print(obj["metadata"])
```

---

## Notebook-Based Analysis

OmniBioAI supports launching **object-aware Jupyter notebooks**.

Typical flow:

1. User clicks **“Analyze in Notebook”** in the OmniBioAI UI
2. Django endpoint generates a notebook
3. JupyterLab opens with the object context preloaded

Inside the notebook:

```python
import os
from omnibioai_sdk import OmniClient

OBJECT_ID = os.environ["OMNIBIOAI_OBJECT_ID"]

c = OmniClient()
obj = c.object_get(OBJECT_ID)

obj["object_type"], obj["metadata"]
```

---

## Running Jupyter for OmniBioAI

Recommended dev command:

```bash
jupyter lab \
  --port 8890 \
  --port-retries=0 \
  --no-browser \
  --notebook-dir . \
  --IdentityProvider.token=devtoken
```

And set:

```bash
export OMNIBIOAI_JUPYTER_BASE=http://127.0.0.1:8890
export OMNIBIOAI_JUPYTER_TOKEN=devtoken
```

---

## Project Structure

```text
omnibioai_sdk/
├── omnibioai_sdk/
│   ├── __init__.py
│   └── client.py
├── pyproject.toml
├── README.md
```

---

## Design Philosophy

* **No magic**: SDK mirrors REST APIs closely
* **Dev-first**: optimized for local servers and notebooks
* **Composable**: meant to be imported into pipelines, workflows, and notebooks
* **Extensible**: new APIs = new methods, not rewrites

---

## Extending the SDK

Add new API calls by extending `OmniClient`:

```python
def workflow_list(self):
    r = requests.get(
        f"{self.base_url}/api/dev/workflows/",
        headers=self.headers,
        timeout=self.timeout
    )
    r.raise_for_status()
    return r.json()
```

No regeneration or codegen required.

---

## Versioning

The SDK follows **semantic versioning**:

* `0.x` → fast iteration
* `1.0+` → stable API surface

---

## License

Apache License 2.0

---

## Status

**Active development**
Used internally by the OmniBioAI workbench and services.

---

## Opening objects in analysis environments

For opening objects in JupyterLab, VS Code, or RStudio, see the
[omnibioai-launcher](https://github.com/man4ish/omnibioai-launcher)
repository. The launcher is a standalone React UI that accepts an
`object_id` via URL parameter and handles environment dispatch.
