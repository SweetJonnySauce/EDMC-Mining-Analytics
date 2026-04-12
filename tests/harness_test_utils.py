from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = REPO_ROOT / "tests"
DEFAULT_TEST_SYSTEM_NAME = "Test Ring"


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
    import config as config_module

    cfg = MockConfig()
    cfg.data["loglevel"] = "INFO"
    config_module.trace_on = []

    import edmc_mining_analytics.plugin as plugin_module

    plugin_module.edmcmaMiningUI = DummyUI
    plugin_module.UpdateManager = DummyUpdateManager

    load = importlib.import_module("load")
    load._plugin._ensure_version_check = lambda: None
    return harness_module, load, cfg


def _parse_iso_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_test_output_root() -> Path:
    token = os.getenv("EDMCMA_HARNESS_USE_REAL_OUTPUT", "").strip().lower()
    if token in {"1", "true", "yes", "on", "real"}:
        return REPO_ROOT
    return TESTS_ROOT


def resolve_test_location_names(system_name: str | None = None) -> dict[str, str]:
    base = (system_name or os.getenv("EDMCMA_HARNESS_SYSTEM_NAME", "")).strip() or DEFAULT_TEST_SYSTEM_NAME
    body = f"{base} A 8"
    return {
        "system": base,
        "body": body,
        "ring": f"{body} A Ring",
        "exit_system": f"{base} Exit",
    }


def _replace_location_names(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_location_names(inner, replacements) for key, inner in value.items()}
    if isinstance(value, list):
        return [_replace_location_names(inner, replacements) for inner in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def _apply_location_overrides(payload: dict[str, Any], *, system_name: str | None = None) -> dict[str, Any]:
    rebased = json.loads(json.dumps(payload))
    location_names = resolve_test_location_names(system_name)
    default_names = resolve_test_location_names(DEFAULT_TEST_SYSTEM_NAME)
    replacements = {
        default_names["ring"]: location_names["ring"],
        default_names["body"]: location_names["body"],
        default_names["exit_system"]: location_names["exit_system"],
        default_names["system"]: location_names["system"],
    }
    return _replace_location_names(rebased, replacements)


def _rebase_payload_timestamps(payload: dict[str, Any]) -> dict[str, Any]:
    rebased = json.loads(json.dumps(payload))
    sequences = [value for value in rebased.values() if isinstance(value, list)]
    timestamps: list[datetime] = []
    for sequence in sequences:
        for entry in sequence:
            if isinstance(entry, dict):
                raw = entry.get("timestamp")
                if isinstance(raw, str):
                    timestamps.append(_parse_iso_timestamp(raw))
    if not timestamps:
        return rebased

    start = min(timestamps)
    target_start = datetime.now(timezone.utc).replace(microsecond=0)

    for sequence in sequences:
        for entry in sequence:
            if not isinstance(entry, dict):
                continue
            raw = entry.get("timestamp")
            if not isinstance(raw, str):
                continue
            entry_time = _parse_iso_timestamp(raw)
            rebased_time = target_start + (entry_time - start)
            entry["timestamp"] = _format_iso_timestamp(rebased_time)
    return rebased


def load_test_journal_events(*, rebase_to_now: bool = True, system_name: str | None = None) -> dict[str, Any]:
    journal_path = TESTS_ROOT / "config" / "journal_events.json"
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    payload = _apply_location_overrides(payload, system_name=system_name)
    return _rebase_payload_timestamps(payload) if rebase_to_now else payload


def _build_harness_fixture_root(temp_root: Path) -> Path:
    fixture_root = temp_root / "harness-fixtures"
    config_dir = fixture_root / "config"
    journal_config_dir = fixture_root / "journal_config"
    journal_folder_dir = fixture_root / "journal_folder"
    config_dir.mkdir(parents=True, exist_ok=True)
    journal_config_dir.mkdir(parents=True, exist_ok=True)
    journal_folder_dir.mkdir(parents=True, exist_ok=True)

    for source in (TESTS_ROOT / "config").glob("*"):
        if source.is_file():
            shutil.copy2(source, config_dir / source.name)

    for source in (TESTS_ROOT / "journal_config").glob("*"):
        if source.is_file():
            shutil.copy2(source, journal_config_dir / source.name)

    custom_journal_events = TESTS_ROOT / "config" / "journal_events.json"
    if custom_journal_events.is_file():
        payload = load_test_journal_events(rebase_to_now=True)
        (journal_config_dir / "journal_events.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    vendored_config = TESTS_ROOT / "edmc" / "EDMarketConnector" / "config.toml"
    if vendored_config.is_file():
        shutil.copy2(vendored_config, config_dir / "config.toml")

    return fixture_root


@contextmanager
def harness_context(*, start_plugin: bool = True) -> Iterator[Tuple[object, object, object]]:
    """Yield (harness, load_module, mock_config) with deterministic cleanup."""

    harness_module, load, cfg = _prepare_load_module()
    with TemporaryDirectory(prefix="edmcma-harness-") as temp_dir:
        fixture_root = _build_harness_fixture_root(Path(temp_dir))
        harness = harness_module.TestHarness(plugin_dir=str(fixture_root))
        if start_plugin:
            load.plugin_start3(str(REPO_ROOT))
        try:
            yield harness, load, cfg
        finally:
            try:
                load.plugin_stop()
            except Exception:
                pass
