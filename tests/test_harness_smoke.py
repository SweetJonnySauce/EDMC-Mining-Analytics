from __future__ import annotations

import importlib
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _import_load_with_dummy_ui():
    """Import load.py with a no-op UI to avoid needing an X/Tk display."""

    from tests.edmc.mocks import MockConfig

    cfg = MockConfig()
    cfg.data["loglevel"] = "INFO"

    import edmc_mining_analytics.plugin as plugin_module

    class DummyUI:
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

    plugin_module.edmcmaMiningUI = DummyUI
    sys.modules.pop("load", None)
    return importlib.import_module("load")


def test_harness_smoke_launch_drone_starts_mining() -> None:
    """Smoke test that the vendored EDMC harness can drive load.py hooks."""

    sys.modules.pop("config", None)
    from tests.harness import TestHarness

    load = _import_load_with_dummy_ui()
    harness_root = REPO_ROOT / "tests"

    harness = TestHarness(plugin_dir=str(harness_root))
    harness.register_journal_handler(
        load.journal_entry,
        commander="HarnessCmdr",
        system="Sol",
        is_beta=False,
    )

    load.plugin_start3(str(REPO_ROOT))
    try:
        harness.fire_event(
            {
                "event": "LaunchDrone",
                "Type": "Prospector",
                "StarSystem": "Sol",
                "timestamp": "3300-01-01T00:00:00Z",
            },
            state={},
        )

        assert load._plugin.state.is_mining is True
        assert load._plugin.state.prospector_launched_count == 1
    finally:
        load.plugin_stop()
