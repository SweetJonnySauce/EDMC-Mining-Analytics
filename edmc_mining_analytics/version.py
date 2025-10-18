"""Centralized plugin metadata and version helpers."""

from __future__ import annotations

import re
from typing import Iterable, Tuple


PLUGIN_VERSION = "0.5.1"
PLUGIN_REPO_URL = "https://github.com/SweetJonnySauce/EDMC-Mining-Analytics"


def display_version(value: str) -> str:
    """Return a version string prefixed with ``v`` if missing."""

    value = value.strip()
    return value if value.lower().startswith("v") else f"v{value}"


def normalize_version(value: str) -> str:
    """Strip a leading ``v``/``V`` and whitespace from a version string."""

    return value.strip().lstrip("vV")


def _version_key(value: str) -> Tuple[Tuple[int, object], ...]:
    """Convert a version string into a sortable key."""

    normalized = normalize_version(value)
    if not normalized:
        return ((0, 0),)
    parts = re.split(r"[._-]", normalized)
    key: list[Tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True if ``latest`` is a higher semantic value than ``current``."""

    return _version_key(latest) > _version_key(current)
