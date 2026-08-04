"""
tests/test_new_namespace_compat.py

SDK Phase 2: proves the omnibioai_sdk -> omnibioai migration is truly
non-breaking, from both directions:
  - every existing `from omnibioai_sdk import OmniClient` caller (already
    covered, unmodified, by tests/test_client.py) keeps working
  - the new `from omnibioai import OmniClient` path resolves to the exact
    same class object, not a copy -- isinstance()/identity checks agree
    regardless of which import path a caller uses
"""
from __future__ import annotations

import omnibioai
import omnibioai_sdk
from omnibioai import OmniClient as NewOmniClient
from omnibioai.legacy import OmniClient as LegacyModuleOmniClient
from omnibioai_sdk import OmniClient as OldOmniClient
from omnibioai_sdk.client import OmniClient as OldOmniClientSubmodule


def test_new_and_old_top_level_imports_are_the_same_class():
    assert NewOmniClient is OldOmniClient


def test_all_four_import_paths_resolve_to_the_same_class():
    assert NewOmniClient is LegacyModuleOmniClient is OldOmniClient is OldOmniClientSubmodule


def test_omnibioai_sdk_package_all_unchanged():
    assert omnibioai_sdk.__all__ == ["OmniClient"]


def test_omnibioai_package_exports_both_new_and_legacy_clients():
    assert set(omnibioai.__all__) == {"OmniBioAI", "OmniClient"}


def test_omnibioai_biai_importable_from_new_namespace():
    from omnibioai import OmniBioAI

    client = OmniBioAI(access_token="tok")
    assert client.access_token == "tok"
