"""Local loader for this plugin's version metadata.

This avoids clashes with other EDMC plugins that also expose a top-level
``version`` module by loading the metadata from this directory explicitly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Tuple


def _load_version_module() -> ModuleType:
    """Load ``version.py`` from the current plugin directory explicitly."""

    version_path = Path(__file__).resolve().with_name("version.py")
    spec = importlib.util.spec_from_file_location(
        "_edmc_mining_analytics_version", version_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load version metadata from {version_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_version = _load_version_module()


PLUGIN_VERSION: str = _version.PLUGIN_VERSION
PLUGIN_REPO_URL: str = _version.PLUGIN_REPO_URL

display_version = _version.display_version
normalize_version = _version.normalize_version
is_newer_version = _version.is_newer_version


__all__ = [
    "PLUGIN_VERSION",
    "PLUGIN_REPO_URL",
    "display_version",
    "normalize_version",
    "is_newer_version",
]
