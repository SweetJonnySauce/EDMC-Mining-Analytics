from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"


class DummyUI:
    """No-op UI used by harness tests to avoid display/Tk requirements."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def build(self, parent):
        return parent

    def build_preferences(self, parent):
        return parent

    def schedule_rate_update(self) -> None:
        return

    def cancel_rate_update(self) -> None:
        return

    def close_histogram_windows(self) -> None:
        return

    def close_local_web_server(self) -> None:
        return

    def refresh(self) -> None:
        return

    def update_version_label(self, *args, **kwargs) -> None:
        return

    def get_root(self):
        return None

    def clear_transient_widgets(self, *args, **kwargs) -> None:
        return

    def set_paused(self, paused, *, source="manual") -> None:
        return


class DummyUpdateManager:
    """Disable auto-update side effects during harness tests."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


def _fresh_harness_module():
    for name in ("load", "tests.harness", "tests.edmc.mocks", "config"):
        sys.modules.pop(name, None)
    harness_module = importlib.import_module("tests.harness")
    harness_module.sleep = lambda _: None
    harness_module.TestHarness._instance = None
    return harness_module


def _prepare_load_module():
    harness_module = _fresh_harness_module()

    # Ensure mocks bootstrap a valid log level for the EDMC logging shim.
    from tests.edmc.mocks import MockConfig

    cfg = MockConfig()
    cfg.data["loglevel"] = "INFO"

    import edmc_mining_analytics.plugin as plugin_module

    plugin_module.edmcmaMiningUI = DummyUI
    plugin_module.UpdateManager = DummyUpdateManager

    load = importlib.import_module("load")
    load._plugin._ensure_version_check = lambda: None
    return harness_module, load, cfg


@contextmanager
def harness_context(*, start_plugin: bool = True) -> Iterator[Tuple[object, object, object]]:
    """Yield (harness, load_module, mock_config) with deterministic cleanup."""

    harness_module, load, cfg = _prepare_load_module()
    harness = harness_module.TestHarness(plugin_dir=str(TESTS_ROOT))
    if start_plugin:
        load.plugin_start3(str(REPO_ROOT))
    try:
        yield harness, load, cfg
    finally:
        try:
            load.plugin_stop()
        except Exception:
            pass
