from __future__ import annotations

from typing import Any

import edmc_mining_analytics.preferences as preferences_module
from edmc_mining_analytics.preferences import (
    LEGACY_OVERLAY_BARS_MAX_ROWS_KEY,
    LEGACY_OVERLAY_SHOW_BARS_KEY,
    OVERLAY_BARS_MAX_ROWS_KEY,
    OVERLAY_SHOW_BARS_KEY,
    PreferencesManager,
)
from edmc_mining_analytics.state import MiningState


class _DummyConfig:
    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self.data: dict[str, Any] = dict(initial or {})

    def get_int(self, key: str | None = None, default: Any = None, **kwargs: Any) -> int:
        resolved_key = key if key is not None else kwargs.get("key")
        return int(self.data.get(resolved_key, default))

    def get_str(self, key: str | None = None, default: Any = None, **kwargs: Any) -> str | None:
        resolved_key = key if key is not None else kwargs.get("key")
        value = self.data.get(resolved_key, default)
        if value is None:
            return None
        return str(value)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


def test_preferences_load_uses_legacy_overlay_keys_when_prefixed_keys_absent(monkeypatch) -> None:
    cfg = _DummyConfig(
        {
            LEGACY_OVERLAY_SHOW_BARS_KEY: 1,
            LEGACY_OVERLAY_BARS_MAX_ROWS_KEY: 7,
        }
    )
    monkeypatch.setattr(preferences_module, "config", cfg)
    state = MiningState()

    PreferencesManager().load(state)

    assert state.overlay_show_bars is True
    assert state.overlay_bars_max_rows == 7


def test_preferences_load_prefers_prefixed_overlay_keys_over_legacy(monkeypatch) -> None:
    cfg = _DummyConfig(
        {
            OVERLAY_SHOW_BARS_KEY: 0,
            OVERLAY_BARS_MAX_ROWS_KEY: 4,
            LEGACY_OVERLAY_SHOW_BARS_KEY: 1,
            LEGACY_OVERLAY_BARS_MAX_ROWS_KEY: 11,
        }
    )
    monkeypatch.setattr(preferences_module, "config", cfg)
    state = MiningState()

    PreferencesManager().load(state)

    assert state.overlay_show_bars is False
    assert state.overlay_bars_max_rows == 4


def test_preferences_save_writes_prefixed_overlay_keys(monkeypatch) -> None:
    cfg = _DummyConfig()
    monkeypatch.setattr(preferences_module, "config", cfg)
    state = MiningState()
    state.overlay_show_bars = True
    state.overlay_bars_max_rows = 12

    PreferencesManager().save(state)

    assert cfg.data[OVERLAY_SHOW_BARS_KEY] == 1
    assert cfg.data[OVERLAY_BARS_MAX_ROWS_KEY] == 12
    assert LEGACY_OVERLAY_SHOW_BARS_KEY not in cfg.data
    assert LEGACY_OVERLAY_BARS_MAX_ROWS_KEY not in cfg.data
