"""
omnibioai -- the OmniBioAI ecosystem SDK.

    from omnibioai import OmniBioAI
    client = OmniBioAI(access_token="jwt-token")

OmniClient (the pre-existing object-registry client) is re-exported here
too, unchanged, for callers migrating from `omnibioai_sdk` who still need
it -- see omnibioai/legacy.py.
"""
from .client import OmniBioAI
from .legacy import OmniClient
from .literature import LiteratureClient
from .models import ModelsClient
from .rag import RAGClient
from .tes import TESClient
from .workflows import WorkflowsClient

__all__ = ["OmniBioAI", "OmniClient", "LiteratureClient", "RAGClient", "ModelsClient", "TESClient", "WorkflowsClient"]
