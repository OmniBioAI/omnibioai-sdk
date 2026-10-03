"""MCP server (omnibioai.mcp_server): the three tools are registered with
their input schemas, each delegates to the matching LiteratureClient call,
and client_from_env reads OMNIBIOAI_API_KEY / OMNIBIOAI_BASE_URL.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from omnibioai.client import DEFAULT_BASE_URL
from omnibioai.mcp_server import build_server, client_from_env


@pytest.fixture
def server():
    client = MagicMock()
    client.literature.ask.return_value = {"answer": "TP53 [PMID:1]"}
    client.literature.studies.return_value = {"studies": ["Oncology"]}
    return build_server(client), client


def test_tools_are_listed_with_schemas(server):
    srv, _ = server
    tools = {t.name: t for t in asyncio.run(srv.list_tools())}
    assert set(tools) == {"answer_with_citations", "find_pmids", "list_studies"}
    assert tools["answer_with_citations"].input_schema["required"] == ["question"]


def test_answer_with_citations(server):
    srv, client = server
    result = asyncio.run(srv.call_tool("answer_with_citations", {"question": "q", "study": "Oncology", "top_k": 3}))
    assert not result.is_error
    assert json.loads(result.content[0].text) == {"answer": "TP53 [PMID:1]"}
    client.literature.ask.assert_called_once_with("q", study="Oncology", top_k=3, mode="rag")


def test_find_pmids_and_list_studies(server):
    srv, client = server
    asyncio.run(srv.call_tool("find_pmids", {"question": "q"}))
    client.literature.ask.assert_called_once_with("q", study="default", top_k=None, mode="pmids_only")
    result = asyncio.run(srv.call_tool("list_studies", {}))
    assert json.loads(result.content[0].text) == {"studies": ["Oncology"]}


def test_client_from_env(monkeypatch):
    monkeypatch.delenv("OMNIBIOAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        client_from_env()
    monkeypatch.setenv("OMNIBIOAI_API_KEY", "omni_sk_" + "a" * 40)
    monkeypatch.delenv("OMNIBIOAI_BASE_URL", raising=False)
    assert client_from_env().base_url == DEFAULT_BASE_URL
    monkeypatch.setenv("OMNIBIOAI_BASE_URL", "https://api.example.com/")
    assert client_from_env().base_url == "https://api.example.com"
