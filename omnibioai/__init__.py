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
from .rag import RAGClient

__all__ = ["OmniBioAI", "OmniClient", "RAGClient"]
