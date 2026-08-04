"""
tests/test_workflows_client.py

Unit tests for omnibioai/workflows/client.py::WorkflowsClient -- covers
request-shape correctness against omnibioai-workflow-bundles's actual
/v1/* contract, the name -> id resolution run() performs (including its
own client-side ResourceNotFoundError for a version that doesn't exist),
the standard error-mapping outcomes, and a full successful
list -> get -> get_inputs -> run -> status lifecycle.
"""
from __future__ import annotations

import json

import responses

from omnibioai import OmniBioAI
from omnibioai.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    ServiceUnavailableError,
)

BASE = "https://gateway.example.com"
WF_URL = f"{BASE}/workflow-bundles"


def _client():
    return OmniBioAI(access_token="tok", base_url=BASE)


class TestWorkflowsUrlDefault:
    def test_defaults_to_base_url_slash_workflow_bundles(self):
        c = _client()
        assert c.workflows.base_url == f"{BASE}/workflow-bundles"

    def test_explicit_workflows_url_overrides_default(self):
        c = OmniBioAI(access_token="tok", base_url=BASE, workflows_url="https://wf.internal.example")
        assert c.workflows.base_url == "https://wf.internal.example"


class TestList:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows",
            json=[{"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}], status=200,
        )
        result = c.workflows.list()
        assert result[0]["name"] == "rna-seq-pipeline"


class TestGet:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/rna-seq-pipeline",
            json=[{"id": 2, "name": "rna-seq-pipeline", "version": "2.0"},
                  {"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}],
            status=200,
        )
        result = c.workflows.get("rna-seq-pipeline")
        assert len(result) == 2
        assert result[0]["version"] == "2.0"

    @responses.activate
    def test_unknown_name_raises_resource_not_found(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/does-not-exist",
            json={"detail": "No workflow named 'does-not-exist'"}, status=404,
        )
        try:
            c.workflows.get("does-not-exist")
            assert False, "expected ResourceNotFoundError"
        except ResourceNotFoundError:
            pass


class TestGetInputs:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/2/inputs",
            json={"inputs": {"reads": "*.fastq"}, "engine": "nextflow", "entrypoint": "main.nf"},
            status=200,
        )
        result = c.workflows.get_inputs(2)
        assert result["engine"] == "nextflow"


class TestRun:
    @responses.activate
    def test_resolves_name_to_newest_version_id_and_runs(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/rna-seq-pipeline",
            json=[{"id": 2, "name": "rna-seq-pipeline", "version": "2.0"},
                  {"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}],
            status=200,
        )
        responses.add(
            responses.POST, f"{WF_URL}/v1/workflows/2/run",
            json={"run_id": "abc12345", "workflow_id": 2, "status": "running"}, status=201,
        )

        result = c.workflows.run("rna-seq-pipeline", inputs={"reads": "sample.fastq"})

        assert result["run_id"] == "abc12345"
        # Ran the NEWEST version (id=2), not the first-listed-by-chance one.
        assert responses.calls[1].request.url == f"{WF_URL}/v1/workflows/2/run"
        sent = json.loads(responses.calls[1].request.body)
        assert sent == {"inputs": {"reads": "sample.fastq"}}

    @responses.activate
    def test_pinned_version_resolves_correct_id(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/rna-seq-pipeline",
            json=[{"id": 2, "name": "rna-seq-pipeline", "version": "2.0"},
                  {"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}],
            status=200,
        )
        responses.add(
            responses.POST, f"{WF_URL}/v1/workflows/1/run",
            json={"run_id": "xyz", "workflow_id": 1, "status": "running"}, status=201,
        )

        c.workflows.run("rna-seq-pipeline", version="1.0")

        assert responses.calls[1].request.url == f"{WF_URL}/v1/workflows/1/run"

    @responses.activate
    def test_unknown_version_raises_resource_not_found_without_extra_call(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/rna-seq-pipeline",
            json=[{"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}], status=200,
        )
        try:
            c.workflows.run("rna-seq-pipeline", version="9.9")
            assert False, "expected ResourceNotFoundError"
        except ResourceNotFoundError:
            pass
        assert len(responses.calls) == 1  # never attempted the run POST

    @responses.activate
    def test_engine_override_forwarded(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/wf",
            json=[{"id": 1, "name": "wf", "version": "1.0"}], status=200,
        )
        responses.add(
            responses.POST, f"{WF_URL}/v1/workflows/1/run",
            json={"run_id": "r1", "workflow_id": 1, "status": "running"}, status=201,
        )
        c.workflows.run("wf", engine="snakemake")
        sent = json.loads(responses.calls[1].request.body)
        assert sent["engine"] == "snakemake"

    @responses.activate
    def test_no_inputs_omits_key(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/wf",
            json=[{"id": 1, "name": "wf", "version": "1.0"}], status=200,
        )
        responses.add(
            responses.POST, f"{WF_URL}/v1/workflows/1/run",
            json={"run_id": "r1", "workflow_id": 1, "status": "running"}, status=201,
        )
        c.workflows.run("wf")
        sent = json.loads(responses.calls[1].request.body)
        assert sent == {}


class TestStatus:
    @responses.activate
    def test_calls_expected_endpoint(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/runs/abc12345",
            json={"run_id": "abc12345", "status": "success", "logs": ["done"]}, status=200,
        )
        result = c.workflows.status("abc12345")
        assert result["status"] == "success"


class TestErrorMapping:
    @responses.activate
    def test_authentication_failure(self):
        c = _client()
        responses.add(responses.GET, f"{WF_URL}/v1/workflows", body="", status=401)
        try:
            c.workflows.list()
            assert False, "expected AuthenticationError"
        except AuthenticationError:
            pass

    @responses.activate
    def test_permission_denied(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows",
            json={"detail": "forbidden"}, status=403,
        )
        try:
            c.workflows.list()
            assert False, "expected PermissionDeniedError"
        except PermissionDeniedError:
            pass

    @responses.activate
    def test_service_unavailable(self):
        c = _client()
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows",
            json={"detail": "db unavailable"}, status=503,
        )
        try:
            c.workflows.list()
            assert False, "expected ServiceUnavailableError"
        except ServiceUnavailableError:
            pass


class TestFullLifecycle:
    @responses.activate
    def test_list_get_inputs_run_status(self):
        """End-to-end: list workflows, inspect one, read its default
        inputs, execute it by name, then poll the resulting run's
        status -- the target architecture's own usage pattern."""
        c = _client()

        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows",
            json=[{"id": 1, "name": "rna-seq-pipeline", "version": "1.0", "enabled": True}], status=200,
        )
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/rna-seq-pipeline",
            json=[{"id": 1, "name": "rna-seq-pipeline", "version": "1.0"}], status=200,
        )
        responses.add(
            responses.GET, f"{WF_URL}/v1/workflows/1/inputs",
            json={"inputs": {"reads": "*.fastq"}, "engine": "nextflow", "entrypoint": "main.nf"}, status=200,
        )
        responses.add(
            responses.POST, f"{WF_URL}/v1/workflows/1/run",
            json={"run_id": "run001", "workflow_id": 1, "status": "running"}, status=201,
        )
        responses.add(
            responses.GET, f"{WF_URL}/v1/runs/run001",
            json={"run_id": "run001", "status": "success", "logs": ["ok"]}, status=200,
        )

        workflows = c.workflows.list()
        assert workflows[0]["name"] == "rna-seq-pipeline"

        defaults = c.workflows.get_inputs(workflows[0]["id"])
        assert defaults["engine"] == "nextflow"

        run = c.workflows.run("rna-seq-pipeline", inputs={"reads": "sample.fastq"})
        assert run["status"] == "running"

        status = c.workflows.status(run["run_id"])
        assert status["status"] == "success"

        assert len(responses.calls) == 5
        for call in responses.calls:
            assert call.request.headers["Authorization"] == "Bearer tok"
