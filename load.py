"""EDMC Mining Analytics load shim.

Keeps the EDMC-required functions in this module while delegating the
implementation to the `edmc_mining_analytics` package.
"""

from __future__ import annotations

from typing import Optional

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

from edmc_mining_analytics.plugin import MiningAnalyticsPlugin

_plugin = MiningAnalyticsPlugin()


def plugin_start3(plugin_dir: str) -> str:
    return _plugin.plugin_start(plugin_dir)


def plugin_app(parent: tk.Widget) -> ttk.Frame:
    return _plugin.plugin_app(parent)


def plugin_prefs(
    parent: tk.Widget,
    cmdr: Optional[str] = None,
    is_beta: bool = False,
) -> tk.Widget:
    return _plugin.plugin_prefs(parent, cmdr, is_beta)


def plugin_stop() -> None:
    _plugin.plugin_stop()


def prefs_changed(cmdr: Optional[str], is_beta: bool) -> None:
    _plugin.prefs_changed(cmdr, is_beta)


def journal_entry(
    cmdr: Optional[str],
    is_beta: bool,
    system: Optional[str],
    station: Optional[str],
    entry: dict,
    state: Optional[dict],
) -> None:
    _plugin.handle_journal_entry(entry, state)
