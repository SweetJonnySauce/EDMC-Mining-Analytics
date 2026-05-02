"""Shared persistence helpers for hotspot favorite rings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

from .logging_utils import get_logger

_log = get_logger("favorite_rings")

FAVORITES_FILENAME = "hotspot_favorite_rings.json"


def resolve_favorite_rings_path(plugin_dir: Path | str | None) -> Path | None:
    if not plugin_dir:
        return None
    return Path(str(plugin_dir)) / "config" / FAVORITES_FILENAME


def load_favorite_rings(path_or_plugin_dir: Path | str | None) -> set[str]:
    path = _coerce_to_favorites_path(path_or_plugin_dir)
    if path is None or not path.exists():
        return set()
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        _log.exception("Failed reading favorite rings file: %s", path)
        return set()

    values: Sequence[object]
    if isinstance(payload, dict):
        candidate = payload.get("favorite_rings")
        values = candidate if isinstance(candidate, list) else []
    elif isinstance(payload, list):
        values = payload
    else:
        values = []

    return _normalize_ring_names(values)


def save_favorite_rings(path_or_plugin_dir: Path | str | None, rings: Iterable[str]) -> set[str]:
    path = _coerce_to_favorites_path(path_or_plugin_dir)
    if path is None:
        raise ValueError("Plugin directory is unavailable for favorite ring persistence")
    normalized = _normalize_ring_names(rings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"favorite_rings": sorted(normalized)}
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return normalized


def _coerce_to_favorites_path(path_or_plugin_dir: Path | str | None) -> Path | None:
    if not path_or_plugin_dir:
        return None
    candidate = Path(str(path_or_plugin_dir))
    if candidate.name == FAVORITES_FILENAME:
        return candidate
    return resolve_favorite_rings_path(candidate)


def _normalize_ring_names(rings: Iterable[object]) -> set[str]:
    normalized: set[str] = set()
    for ring in rings:
        text = str(ring or "").strip()
        if text:
            normalized.add(text)
    return normalized
