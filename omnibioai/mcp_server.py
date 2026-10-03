"""omnibioai/mcp_server.py

An MCP (Model Context Protocol) server exposing the public Literature AI
API as tools, so Claude, ChatGPT and other MCP clients can ask OmniBioAI
for PubMed-cited answers. Every tool call goes through the same metered
/v1/literature API as the SDK (one billable answer per answer tool call),
authenticated with an omni_sk_ API key.

Run it (stdio, the transport desktop MCP clients launch):

    pip install "omnibioai-sdk[mcp]"
    OMNIBIOAI_API_KEY=omni_sk_... OMNIBIOAI_BASE_URL=https://<gateway> omnibioai-mcp

The `mcp` package is an optional extra and only imported here, so
`import omnibioai` never requires it.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from .client import DEFAULT_BASE_URL, OmniBioAI

SERVER_NAME = "omnibioai"
INSTRUCTIONS = (
    "Biomedical literature tools backed by PubMed. Use answer_with_citations for "
    "questions that need an evidence-based answer; every claim carries its PubMed ID. "
    "Use find_pmids when only the relevant papers are needed, and list_studies to see "
    "which research domains can be searched."
)


def build_server(client: OmniBioAI) -> Any:
    """The MCP server, with its tools bound to `client`."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS)

    @server.tool(description="Answer a biomedical question from PubMed abstracts, citing PMIDs. Billed per answer.")
    def answer_with_citations(question: str, study: str = "default", top_k: Optional[int] = None) -> dict:
        return client.literature.ask(question, study=study, top_k=top_k, mode="rag")

    @server.tool(description="Return the PubMed IDs most relevant to a question, without an answer. Billed per call.")
    def find_pmids(question: str, study: str = "default", top_k: Optional[int] = None) -> dict:
        return client.literature.ask(question, study=study, top_k=top_k, mode="pmids_only")

    @server.tool(description="List the research domains (studies) that can be searched. Free.")
    def list_studies() -> dict:
        return client.literature.studies()

    return server


def client_from_env() -> OmniBioAI:
    api_key = os.environ.get("OMNIBIOAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OMNIBIOAI_API_KEY to an omni_sk_ API key.")
    return OmniBioAI(api_key=api_key, base_url=os.environ.get("OMNIBIOAI_BASE_URL", DEFAULT_BASE_URL))


def main() -> None:  # pragma: no cover - process entry point
    build_server(client_from_env()).run(transport=os.environ.get("OMNIBIOAI_MCP_TRANSPORT", "stdio"))
