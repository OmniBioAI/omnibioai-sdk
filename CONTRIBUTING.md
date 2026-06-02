# Contributing to omnibioai-sdk

Thank you for your interest in contributing. This guide reflects the actual structure of the Python SDK — read it before writing any code.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Client architecture](#client-architecture)
- [Adding a new API method](#adding-a-new-api-method)
- [Testing](#testing)
- [Building and publishing](#building-and-publishing)
- [Code quality](#code-quality)
- [PR checklist](#pr-checklist)

---

## Code of conduct

Be respectful, constructive, and professional. Harassment or dismissive communication will not be tolerated. Assume good faith.

---

## Getting started

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10+ |
| pip | 23+ |

### Install in editable mode with dev extras

```bash
git clone https://github.com/man4ish/omnibioai_sdk
cd omnibioai-sdk

python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

The `[dev]` extra installs `pytest`, `pytest-cov`, `responses`, `build`, and `twine` as defined in `pyproject.toml`.

### Environment variables

`OmniClient` reads two env vars at instantiation time (both have hardcoded defaults for local dev):

| Variable | Default | Purpose |
|---|---|---|
| `OMNIBIOAI_BASE_URL` | `http://127.0.0.1:8001` | Base URL of the OmniBioAI API |
| `OMNIBIOAI_TOKEN` | `dev` | Bearer token for authentication |

The dev defaults point to the `api_dev` Django module in the `omnibioai` repo, which runs on port 8001.

---

## Repository layout

```
omnibioai-sdk/
├── omnibioai_sdk/
│   ├── __init__.py      ← exports OmniClient
│   └── client.py        ← OmniClient class — all API methods live here
├── tests/
│   ├── __init__.py
│   └── test_client.py   ← all tests — uses `responses` to mock HTTP
├── pyproject.toml       ← build system (hatchling), project metadata, pytest config
└── README.md
```

---

## Client architecture

All SDK logic lives in `omnibioai_sdk/client.py`. There is intentionally one class: `OmniClient`.

```python
class OmniClient:
    def __init__(self, base_url=None, token=None, timeout=60):
        # base_url: explicit arg → OMNIBIOAI_BASE_URL env var → default
        # token:    explicit arg → OMNIBIOAI_TOKEN env var → "dev"
        ...

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
```

Key design decisions that must be preserved:

- `base_url` strips a trailing `/` at init time (`rstrip("/")`) — always construct URLs with a leading `/` on the path
- All methods call `r.raise_for_status()` before returning — callers get `requests.HTTPError` on 4xx/5xx
- `headers` is a `@property` — it is recomputed on each access (allows token mutation after init)
- `timeout` defaults to 60 seconds — pass it on every `requests` call

---

## Adding a new API method

### 1. Add the method to `OmniClient` in `client.py`

Follow the existing pattern exactly:

```python
def runs_list(self, plugin_slug: str) -> dict:
    r = requests.get(
        f"{self.base_url}/api/dev/runs/{plugin_slug}/",
        headers=self.headers,
        timeout=self.timeout,
    )
    r.raise_for_status()
    return r.json()
```

- Use type annotations on all parameters and return values
- Use `self.headers`, `self.base_url`, `self.timeout` — never hardcode these
- Call `r.raise_for_status()` before accessing the response body

### 2. Export from `__init__.py` if adding a new public class

`OmniClient` is currently the only public symbol. If you add a new top-level class (e.g. `OmniAsyncClient`), add it to `__all__` in `__init__.py`:

```python
from .client import OmniClient, OmniAsyncClient

__all__ = ["OmniClient", "OmniAsyncClient"]
```

### 3. Write tests (see [Testing](#testing))

Every new method needs tests covering:
- Successful 200 response
- 4xx error raises `requests.HTTPError`
- 5xx error raises `requests.HTTPError`
- Correct URL constructed (check `responses.calls[0].request.url`)
- Correct `Authorization` header sent

---

## Testing

Tests live in `tests/test_client.py` and use the `responses` library to intercept HTTP calls — no real network requests, no running server needed.

### Run tests

```bash
pytest
```

The `pyproject.toml` configures pytest to:
- Run `tests/` as the test directory
- Collect coverage for `omnibioai_sdk/`
- Fail if coverage drops below **95%**
- Report missing lines

### Run with explicit coverage report

```bash
pytest --cov=omnibioai_sdk --cov-report=term-missing
```

### Test patterns

**Success case:**

```python
@responses.activate
def test_runs_list_success():
    c = OmniClient(base_url=BASE, token="dev", timeout=3)
    responses.add(
        responses.GET,
        f"{BASE}/api/dev/runs/my_plugin/",
        json={"count": 1, "items": [{"run_id": "abc"}]},
        status=200,
    )
    out = c.runs_list("my_plugin")
    assert out["count"] == 1
    assert responses.calls[0].request.headers["Authorization"] == "Bearer dev"
```

**Error case:**

```python
@responses.activate
def test_runs_list_401_raises():
    c = OmniClient(base_url=BASE, token="bad")
    responses.add(responses.GET, f"{BASE}/api/dev/runs/my_plugin/", json={}, status=401)
    with pytest.raises(requests.HTTPError):
        c.runs_list("my_plugin")
```

**Env var isolation** — every test that involves env vars should use the `_clean_env` autouse fixture already defined in `test_client.py` — it strips `OMNIBIOAI_BASE_URL` and `OMNIBIOAI_TOKEN` so tests are hermetic.

### Coverage requirement

The `pyproject.toml` sets `--cov-fail-under=95`. New code must maintain this threshold. Uncoverable lines can be marked `# pragma: no cover` only for the patterns listed in `[tool.coverage.report].exclude_lines` (e.g. `raise NotImplementedError`, `if __name__ == "__main__":`).

---

## Building and publishing

### Build the wheel and sdist

```bash
python -m build
```

Outputs to `dist/`:
- `omnibioai_sdk-<version>-py3-none-any.whl`
- `omnibioai_sdk-<version>.tar.gz`

### Bump the version

Edit `version` in `pyproject.toml` before publishing. Follow semver:
- **Patch** (`0.1.x`): bug fixes, no API changes
- **Minor** (`0.x.0`): new methods or parameters (backwards compatible)
- **Major** (`x.0.0`): breaking changes to existing methods or init signature

### Publish (PyPI or internal registry)

```bash
twine upload dist/*
```

Ensure `~/.pypirc` or environment variables (`TWINE_USERNAME`, `TWINE_PASSWORD`) are configured for the target registry.

---

## Code quality

- **PEP 8** for all Python code
- **Type annotations** on all public methods — parameters and return values
- **`requests.raise_for_status()`** on every HTTP response before accessing the body
- **No direct imports of `os.environ`** in method bodies — read env vars only in `__init__`
- **No mutable default arguments** in method signatures
- **Docstrings:** class-level docstrings on `OmniClient` are sufficient; individual method docstrings optional if the name and types are self-explanatory

Format before committing:

```bash
python -m black omnibioai_sdk/ tests/
python -m isort omnibioai_sdk/ tests/
```

---

## PR checklist

- [ ] New method added to `OmniClient` in `client.py` following existing patterns
- [ ] `self.headers`, `self.base_url`, `self.timeout` used — no hardcoded values
- [ ] `r.raise_for_status()` called before accessing response body
- [ ] Tests added covering 200, 4xx, and 5xx cases
- [ ] `pytest` passes with coverage ≥ 95%: `pytest --cov=omnibioai_sdk`
- [ ] Type annotations on all new parameters and return values
- [ ] `version` in `pyproject.toml` bumped if releasing
- [ ] Links to the issue: `Closes #<issue-number>`

---

## Questions

Open a GitHub issue or tag `@man4ish` in the relevant issue.
