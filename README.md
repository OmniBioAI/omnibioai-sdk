# OmniBioAI SDK

> **0.2.0: new `omnibioai` package.** This SDK is migrating to a unified,
> ecosystem-wide client under a new import path:
> ```python
> from omnibioai import OmniBioAI
>
> client = OmniBioAI(access_token="jwt-token")
>
> result = client.rag.query("BRCA1 pathway analysis")
> ```
> `OmniBioAI` handles token refresh and error normalization across
> OmniBioAI services. `.rag`, `.models`, `.tes`, and `.workflows` are all
> available now. Note `client.models` is task-scoped
> (`client.models.get(task, ref)`), not a bare-name lookup --
> `omnibioai-model-registry`'s actual API has no cross-task name search,
> so the SDK mirrors its real shape rather than the target example's
> simplified one. `.tes` (low-level tool execution, e.g.
> `client.tes.submit(tool_id, inputs={...})`) and `.workflows` (high-level
> named pipelines, e.g. `client.workflows.run(workflow_name, inputs={})`)
> are deliberately kept as two separate clients -- see each client's own
> module docstring. `.workflows`'s target service
> (`omnibioai-workflow-bundles`) has no confirmed API Gateway route yet;
> pass `workflows_url=` explicitly until it does. **Nothing existing
> breaks**: the object-registry client documented below is unchanged and
> fully supported, importable from
> either `omnibioai_sdk` (as before) or `omnibioai`
> (`from omnibioai import OmniClient`) -- both resolve to the exact same
> class.

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
# From GitHub Packages (requires token with read:packages scope)
pip install omnibioai-sdk \
  --index-url https://pip.pkg.github.com/OmniBioAI/simple/

# Or directly from GitHub
pip install git+https://github.com/OmniBioAI/omnibioai-sdk.git

# Or locally during development
pip install -e .
```

> **Note:** `omnibioai-sdk` is not currently published to PyPI.
> Install from GitHub or use the local editable install during development.

---

## Quick Start

```python
from omnibioai_sdk import OmniClient

c = OmniClient(
    base_url="http://127.0.0.1:8080",   # api-gateway
    token="your-jwt-token"               # obtain via POST /auth/login
)

objects = c.objects_list()
print(objects["count"])
```

> **Note:** All requests go through `api-gateway` (port 8080) which
> enforces JWT authentication and routes to the correct backend service.
> Never point the SDK directly at individual services (auth-service,
> workbench etc.) in production.

### Getting a token

```python
import requests

resp = requests.post("http://127.0.0.1:8080/auth/login",
    json={"email": "admin@example.com", "password": "yourpassword"})
token = resp.json()["access_token"]

from omnibioai_sdk import OmniClient
c = OmniClient(base_url="http://127.0.0.1:8080", token=token)
```

Or via environment variables:

```bash
export OMNIBIOAI_BASE_URL=http://127.0.0.1:8080
export OMNIBIOAI_TOKEN=your-jwt-token
```

---

## Authentication

The legacy `OmniClient` (Object Registry API, below) uses simple
**header-based authentication** — a single static token, no refresh:

```text
Authorization: Bearer dev
```

You can pass credentials explicitly or via environment variables.

### Environment Variables (recommended)

```bash
export OMNIBIOAI_BASE_URL=http://127.0.0.1:8080   # api-gateway
export OMNIBIOAI_TOKEN=dev
```

Then simply:

```python
c = OmniClient()
```

### The new `OmniBioAI` client's auth model

`OmniBioAI` (`.rag`/`.models`/`.tes`/`.workflows`) takes an explicit
access/refresh token pair instead and manages them automatically:

```python
from omnibioai import OmniBioAI

client = OmniBioAI(
    access_token="jwt-token",
    refresh_token="refresh-token",   # optional but required for auto-refresh
)
```

- **One shared session, one token pair.** All four sub-clients are
  constructed against the same `AuthenticatedSession`/`TokenPair` — a
  refresh triggered by any one of them (e.g. `.rag.query(...)`) is
  immediately visible to the others on their very next call.
- **Refresh-on-401, once.** A `401` triggers exactly one refresh call
  against `auth_url + /auth/refresh`; a second `401` (or a failed
  refresh) raises `AuthenticationError` rather than retrying again —
  mirroring `omnibioai-auth`'s own refresh-token-family-compromise
  contract, where re-presenting an already-rotated refresh token is
  treated as compromise, not a retriable error.
- **`client.access_token` / `client.refresh_token`** reflect the
  *current* tokens, which may differ from what you passed to `__init__`
  after the first automatic refresh (`omnibioai-auth` refresh tokens are
  single-use and rotate on every refresh).
- **`X-Trace-Id`** is generated fresh per call (or supplied by the
  caller) and recorded on `client.session.last_trace_id`, matching the
  header every IAM Foundation service (gateway, RAG, TES, …) already
  reads — useful for correlating one client-side error across services.
- **No local JWT verification.** The SDK never decodes or verifies the
  access/refresh token itself — that's the API Gateway's and each
  target service's job, not this client's.

---

## URLs by environment

| Environment | Base URL | Notes |
|-------------|----------|-------|
| Local development | `http://127.0.0.1:8080` | api-gateway direct |
| Via nginx (Studio) | `http://localhost/_svc/gateway` | JWT required |
| Production | `https://api.omnibioai.org` | TLS + JWT required |

Always use the api-gateway URL for `base_url` — never point directly at
individual services (workbench :8000, etc.).

**Two deliberate exceptions:**

- `OmniBioAI`'s login/refresh/logout calls go to a *separate* `auth_url`
  (default `https://auth.omnibioai.org`), not `base_url` — the API
  Gateway's `SERVICE_MAP` has no `auth` entry, so those routes aren't
  reachable through it today. Override with `OmniBioAI(..., auth_url=...)`
  for non-default deployments.
- `.workflows` defaults to `{base_url}/workflow-bundles`, but
  `omnibioai-workflow-bundles` has no *confirmed* route in the Gateway's
  `SERVICE_MAP` yet — pass `OmniBioAI(..., workflows_url=...)` explicitly
  until it does.

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
omnibioai-sdk/
├── omnibioai/                  # new, ecosystem-wide package (0.2.0)
│   ├── __init__.py             # exports OmniBioAI, OmniClient, RAGClient,
│   │                            # ModelsClient, TESClient, WorkflowsClient
│   ├── client.py                # OmniBioAI — top-level client, owns one
│   │                            # shared AuthenticatedSession
│   ├── legacy.py                # OmniClient, relocated unchanged from
│   │                            # omnibioai_sdk/client.py — see below
│   ├── exceptions.py
│   ├── _base.py
│   ├── auth/
│   │   ├── session.py           # AuthenticatedSession — auth header
│   │   │                        # injection, refresh-on-401, X-Trace-Id
│   │   └── tokens.py            # TokenPair — mutated in place on refresh
│   ├── rag/client.py            # RAGClient — .query(...)
│   ├── models/client.py         # ModelsClient — .get(task, ref), task-scoped
│   ├── tes/client.py            # TESClient — .submit(tool_id, inputs=...)
│   └── workflows/client.py      # WorkflowsClient — .run(workflow_name, inputs=...)
├── omnibioai_sdk/                # pre-existing package, kept for compatibility
│   ├── __init__.py               # re-exports OmniClient from omnibioai/legacy.py
│   └── client.py                 # re-exports OmniClient from omnibioai/legacy.py
├── tests/
├── pyproject.toml
└── README.md
```

`omnibioai_sdk/` is not a separate, unmaintained package — both of its
modules now just re-export `OmniClient` from `omnibioai/legacy.py`, so
`from omnibioai_sdk import OmniClient` (every existing caller's import)
keeps working unchanged and indefinitely, alongside the new
`from omnibioai import OmniClient` path.

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

## Related packages

| Package | Purpose |
|---------|---------|
| `omnibioai-launcher` | Browser UI — alternative to SDK for interactive use |
| `omnibioai-model-registry` | Backs `.models` — ML model versioning (`omr` CLI + its own Python client) |
| `omnibioai-rag` | Backs `.rag` — PubMed/literature query API |
| `omnibioai-tes` | Backs `.tes` — low-level, tool_id-addressed execution |
| `omnibioai-workflow-bundles` | Backs `.workflows` — named/versioned pipeline execution; no confirmed API Gateway route yet, see [URLs by environment](#urls-by-environment) |
| `omnibioai-studio` | Desktop app — manages the full stack the SDK connects to |
| `omnibioai-iam-client` | Internal service auth SDK (for service-to-service calls) — not used by this SDK itself; see [Authentication](#authentication) |

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
[omnibioai-launcher](https://github.com/OmniBioAI/omnibioai-launcher)
repository. The launcher is a standalone React UI that accepts an
`object_id` via URL parameter and handles environment dispatch.
