"""
Backward-compatibility package (SDK Phase 2). The canonical implementation
has moved to the `omnibioai` package (`from omnibioai import OmniBioAI`,
the new ecosystem-wide client) -- this package now only re-exports
OmniClient so every existing `from omnibioai_sdk import OmniClient` caller
is unaffected. See omnibioai/legacy.py for the actual implementation.
"""
from omnibioai.legacy import OmniClient

__all__ = ["OmniClient"]
