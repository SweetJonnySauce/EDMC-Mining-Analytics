"""Formatting helpers for compact numeric display."""

from __future__ import annotations

from typing import Optional


_UNITS = (
    (1_000_000_000_000.0, "T"),
    (1_000_000_000.0, "B"),
    (1_000_000.0, "M"),
    (1_000.0, "K"),
)


def format_compact_number(value: Optional[float], *, default: str = "--") -> str:
    """Return a compact human-readable number (e.g., 4.3M)."""

    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default

    sign = "-" if numeric < 0 else ""
    magnitude = abs(numeric)
    for threshold, suffix in _UNITS:
        if magnitude >= threshold:
            scaled = magnitude / threshold
            if scaled >= 100:
                formatted = f"{scaled:.0f}"
            else:
                formatted = f"{scaled:.1f}".rstrip("0").rstrip(".")
            return f"{sign}{formatted}{suffix}"
    return f"{sign}{int(round(magnitude)):,}"


__all__ = ["format_compact_number"]
