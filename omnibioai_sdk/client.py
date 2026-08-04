"""
Backward-compatibility shim (SDK Phase 2). OmniClient's real implementation
now lives in omnibioai/legacy.py -- this re-export exists so
`from omnibioai_sdk.client import OmniClient` and `from omnibioai_sdk
import OmniClient` keep working unchanged for every existing caller. Not a
copy: this is the exact same class object omnibioai.legacy defines, so
isinstance()/identity checks against either import path agree.
"""
from omnibioai.legacy import OmniClient

__all__ = ["OmniClient"]
