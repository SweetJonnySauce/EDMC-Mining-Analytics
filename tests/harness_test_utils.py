from __future__ import annotations

import importlib
import json
import os
import random
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
GENERATED_PLATINUM_SESSION_PATH = TESTS_ROOT / "config" / "generated_platinum_session.json"
PLATINUM_ASTEROID_COUNT_MIN = 15
PLATINUM_ASTEROID_COUNT_MAX = 25
PLATINUM_PERCENTAGE_MIN = 6.214476
PLATINUM_PERCENTAGE_MAX = 66.666672
PLATINUM_ABSENT_RATIO = 0.30
PLATINUM_PRESENT_AVERAGE_MIN = 28.5
PLATINUM_PRESENT_AVERAGE_MAX = 31.5

_generated_platinum_session_cache: dict[str, Any] | None = None


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


def _resolve_platinum_seed(seed: int | None = None) -> int:
    if seed is not None:
        return int(seed)
    raw = os.getenv("EDMCMA_HARNESS_PLATINUM_SEED", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            return sum((index + 1) * ord(char) for index, char in enumerate(raw))
    return random.SystemRandom().randrange(0, 2**31)


def _classify_platinum_content(percentage: float) -> str:
    if percentage >= 50:
        return "High"
    if percentage >= 20:
        return "Medium"
    return "Low"


def _clip_platinum_percentage(value: float) -> float:
    return max(PLATINUM_PERCENTAGE_MIN, min(PLATINUM_PERCENTAGE_MAX, value))


def _generate_present_platinum_percentages(rng: random.Random, present_count: int) -> list[float]:
    target_average = rng.uniform(29.25, 30.75)
    for _ in range(256):
        values = [_clip_platinum_percentage(rng.gauss(target_average, 9.0)) for _ in range(present_count)]
        average = sum(values) / present_count if present_count else 0.0
        if PLATINUM_PRESENT_AVERAGE_MIN <= average <= PLATINUM_PRESENT_AVERAGE_MAX:
            return [round(value, 6) for value in values]

    values = [_clip_platinum_percentage(rng.gauss(target_average, 9.0)) for _ in range(present_count)]
    average = sum(values) / present_count if present_count else 0.0
    adjustment = target_average - average
    adjusted = [_clip_platinum_percentage(value + adjustment) for value in values]
    return [round(value, 6) for value in adjusted]


def build_generated_platinum_session_profile(*, seed: int | None = None) -> dict[str, Any]:
    resolved_seed = _resolve_platinum_seed(seed)
    rng = random.Random(resolved_seed)
    asteroid_count = rng.randint(PLATINUM_ASTEROID_COUNT_MIN, PLATINUM_ASTEROID_COUNT_MAX)
    absent_count = max(1, min(asteroid_count - 1, round(asteroid_count * PLATINUM_ABSENT_RATIO)))
    present_count = asteroid_count - absent_count
    present_percentages = _generate_present_platinum_percentages(rng, present_count)
    platinum_yields: list[float | None] = [None] * asteroid_count
    for index in rng.sample(range(asteroid_count), present_count):
        platinum_yields[index] = present_percentages.pop()

    content_summary = {"High": 0, "Medium": 0, "Low": 0}
    for percentage in platinum_yields:
        if percentage is None:
            content_summary["Low"] += 1
            continue
        content_summary[_classify_platinum_content(percentage)] += 1
    realized_present = [float(value) for value in platinum_yields if value is not None]
    return {
        "seed": resolved_seed,
        "asteroid_count": asteroid_count,
        "platinum_absent_count": absent_count,
        "platinum_present_count": present_count,
        "platinum_percentage_min": PLATINUM_PERCENTAGE_MIN,
        "platinum_percentage_max": PLATINUM_PERCENTAGE_MAX,
        "platinum_present_average": round(sum(realized_present) / len(realized_present), 6),
        "platinum_yields": platinum_yields,
        "platinum_percentages": realized_present,
        "content_summary": content_summary,
        "generated_at": _format_iso_timestamp(datetime.now(timezone.utc)),
    }


def _build_content_summary_from_yields(platinum_yields: list[float | None]) -> dict[str, int]:
    content_summary = {"High": 0, "Medium": 0, "Low": 0}
    for percentage in platinum_yields:
        if percentage is None:
            content_summary["Low"] += 1
            continue
        content_summary[_classify_platinum_content(float(percentage))] += 1
    return content_summary


def _make_prospect_key(entry: dict[str, Any]) -> tuple[str, tuple[tuple[str, float], ...]] | None:
    materials = entry.get("Materials")
    if not isinstance(materials, list):
        return None

    items: list[tuple[str, float]] = []
    for material in materials:
        if not isinstance(material, dict):
            continue
        name_raw = material.get("Name")
        proportion_raw = material.get("Proportion")
        if not isinstance(name_raw, str):
            continue
        try:
            proportion = float(proportion_raw)
        except (TypeError, ValueError):
            continue
        items.append((name_raw.lower(), round(proportion, 4)))

    if not items:
        return None

    items.sort()
    body = entry.get("Body")
    body_component = str(body) if isinstance(body, str) else ""
    content = str(entry.get("Content", ""))
    content_localised = str(entry.get("Content_Localised", ""))
    return ("|".join(filter(None, (body_component, content, content_localised))), tuple(items))


def load_generated_platinum_session_profile(*, force_refresh: bool = False) -> dict[str, Any]:
    global _generated_platinum_session_cache
    if _generated_platinum_session_cache is not None and not force_refresh:
        return json.loads(json.dumps(_generated_platinum_session_cache))

    profile = build_generated_platinum_session_profile()
    journal_path = TESTS_ROOT / "config" / "journal_events.json"
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    _apply_generated_platinum_profile(payload, profile)
    GENERATED_PLATINUM_SESSION_PATH.write_text(
        json.dumps(profile, indent=2) + "\n",
        encoding="utf-8",
    )
    _generated_platinum_session_cache = profile
    return json.loads(json.dumps(profile))


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


def _find_prospect_phase_bounds(sequence: list[dict[str, Any]]) -> tuple[int, int]:
    start_index = next(
        index
        for index, entry in enumerate(sequence)
        if entry.get("event") == "LaunchDrone" and entry.get("Type") == "Prospector"
    )
    end_index = next(
        index
        for index, entry in enumerate(sequence[start_index + 1:], start_index + 1)
        if entry.get("event") == "Cargo"
    )
    return start_index, end_index


def _split_prospect_blocks(sequence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    start_index, end_index = _find_prospect_phase_bounds(sequence)
    prefix = sequence[:start_index]
    section = sequence[start_index:end_index]
    suffix = sequence[end_index:]

    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for entry in section:
        if entry.get("event") == "LaunchDrone" and entry.get("Type") == "Prospector":
            if current:
                blocks.append(current)
            current = [entry]
            continue
        current.append(entry)
    if current:
        blocks.append(current)

    productive_blocks = [
        block
        for block in blocks
        if any(entry.get("event") == "ProspectedAsteroid" for entry in block)
    ]
    trailing_block = next(
        (block for block in blocks if not any(entry.get("event") == "ProspectedAsteroid" for entry in block)),
        [],
    )
    return prefix, productive_blocks, trailing_block, suffix


def _retime_block(block: list[dict[str, Any]], new_start: datetime) -> list[dict[str, Any]]:
    original_start = _parse_iso_timestamp(block[0]["timestamp"])
    cloned: list[dict[str, Any]] = []
    for entry in block:
        copy = json.loads(json.dumps(entry))
        delta = _parse_iso_timestamp(entry["timestamp"]) - original_start
        copy["timestamp"] = _format_iso_timestamp(new_start + delta)
        cloned.append(copy)
    return cloned


def _adjust_non_platinum_materials(materials: list[dict[str, Any]], platinum_percentage: float, *, asteroid_index: int = 0) -> list[dict[str, Any]]:
    if not materials:
        return []
    remaining_budget = max(0.0, 100.0 - platinum_percentage)
    total = sum(max(0.0, float(material.get("Proportion") or 0.0)) for material in materials)
    scale = min(1.0, (remaining_budget / total)) if total > 0 else 1.0
    adjusted: list[dict[str, Any]] = []
    for material_index, material in enumerate(materials):
        copy = json.loads(json.dumps(material))
        proportion = max(0.0, float(copy.get("Proportion") or 0.0)) * scale
        proportion += (asteroid_index + material_index + 1) * 0.0001
        copy["Proportion"] = round(proportion, 6)
        adjusted.append(copy)
    return adjusted


def _build_absent_platinum_materials(materials: list[dict[str, Any]], *, asteroid_index: int = 0) -> list[dict[str, Any]]:
    non_platinum = [
        json.loads(json.dumps(material))
        for material in materials
        if str(material.get("Name") or "").strip().lower() != "platinum"
    ][:2]
    if non_platinum:
        return _adjust_non_platinum_materials(non_platinum, 0.0, asteroid_index=asteroid_index)
    return [
        {
            "Name": "Gold",
            "Name_Localised": "Gold",
            "Proportion": round(22.0 + ((asteroid_index + 1) * 0.0001), 6),
        }
    ]


def _apply_platinum_percentage(prospect_event: dict[str, Any], platinum_percentage: float | None, *, asteroid_index: int = 0) -> dict[str, Any]:
    event = json.loads(json.dumps(prospect_event))
    materials = event.get("Materials") or []
    if platinum_percentage is None:
        event["Content"] = "Low"
        event["Materials"] = _build_absent_platinum_materials(materials, asteroid_index=asteroid_index)
        return event

    non_platinum = [
        json.loads(json.dumps(material))
        for material in materials
        if str(material.get("Name") or "").strip().lower() != "platinum"
    ][:2]
    adjusted_non_platinum = _adjust_non_platinum_materials(non_platinum, platinum_percentage, asteroid_index=asteroid_index)
    event["Content"] = _classify_platinum_content(platinum_percentage)
    event["Materials"] = [
        {
            "Name": "Platinum",
            "Name_Localised": "Platinum",
            "Proportion": round(platinum_percentage, 6),
        },
        *adjusted_non_platinum,
    ]
    return event


def _ensure_unique_prospect_event(
    prospect_event: dict[str, Any],
    used_keys: set[tuple[str, tuple[tuple[str, float], ...]]],
) -> dict[str, Any]:
    event = json.loads(json.dumps(prospect_event))
    materials = event.get("Materials")
    if not isinstance(materials, list) or not materials:
        return event

    preferred_index = next(
        (
            index
            for index, material in enumerate(materials)
            if str(material.get("Name") or "").strip().lower() != "platinum"
        ),
        0,
    )

    for _ in range(128):
        key = _make_prospect_key(event)
        if key is None or key not in used_keys:
            if key is not None:
                used_keys.add(key)
            return event
        try:
            current = float(materials[preferred_index].get("Proportion") or 0.0)
        except (TypeError, ValueError):
            current = 0.0
        materials[preferred_index]["Proportion"] = round(current + 0.00011, 6)

    key = _make_prospect_key(event)
    if key is not None:
        used_keys.add(key)
    return event


def _apply_generated_platinum_profile(payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    rebased = json.loads(json.dumps(payload))
    sequence = rebased.get("sample_mining_session")
    if not isinstance(sequence, list):
        return rebased

    prefix, productive_blocks, trailing_block, suffix = _split_prospect_blocks(sequence)
    if not productive_blocks or not trailing_block:
        return rebased

    start_time = _parse_iso_timestamp(productive_blocks[0][0]["timestamp"])
    productive_spacing = timedelta(seconds=12)
    original_lost_time = _parse_iso_timestamp(trailing_block[0]["timestamp"])
    original_last_productive_time = _parse_iso_timestamp(productive_blocks[-1][0]["timestamp"])
    lost_gap = original_lost_time - original_last_productive_time

    generated_phase: list[dict[str, Any]] = []
    collection_launches = 0
    realized_yields: list[float | None] = []
    used_prospect_keys: set[tuple[str, tuple[tuple[str, float], ...]]] = set()
    for index, percentage in enumerate(profile["platinum_yields"]):
        template_block = productive_blocks[index % len(productive_blocks)]
        block_start = start_time + (productive_spacing * index)
        generated_block = _retime_block(template_block, block_start)
        for event_index, event in enumerate(generated_block):
            if event.get("event") == "ProspectedAsteroid":
                generated_block[event_index] = _ensure_unique_prospect_event(
                    _apply_platinum_percentage(event, percentage, asteroid_index=index),
                    used_prospect_keys,
                )
                materials = generated_block[event_index].get("Materials") or []
                platinum_material = next(
                    (
                        material
                        for material in materials
                        if str(material.get("Name") or "").strip().lower() == "platinum"
                    ),
                    None,
                )
                realized_yields.append(
                    round(float(platinum_material["Proportion"]), 6) if platinum_material else None
                )
            elif event.get("event") == "LaunchDrone" and event.get("Type") == "Collection":
                collection_launches += 1
        generated_phase.extend(generated_block)

    last_block_start = start_time + (productive_spacing * (profile["asteroid_count"] - 1))
    generated_trailing_block = _retime_block(trailing_block, last_block_start + lost_gap)
    trailing_shift = _parse_iso_timestamp(generated_trailing_block[0]["timestamp"]) - original_lost_time

    generated_suffix: list[dict[str, Any]] = []
    for entry in suffix:
        copy = json.loads(json.dumps(entry))
        copy["timestamp"] = _format_iso_timestamp(_parse_iso_timestamp(copy["timestamp"]) + trailing_shift)
        generated_suffix.append(copy)

    profile["prospector_launches"] = int(profile["asteroid_count"]) + 1
    profile["collection_launches"] = collection_launches
    profile["platinum_yields"] = realized_yields
    profile["platinum_percentages"] = [value for value in realized_yields if value is not None]
    profile["platinum_absent_count"] = sum(1 for value in realized_yields if value is None)
    profile["platinum_present_count"] = len(profile["platinum_percentages"])
    if profile["platinum_percentages"]:
        profile["platinum_present_average"] = round(
            sum(profile["platinum_percentages"]) / len(profile["platinum_percentages"]),
            6,
        )
    profile["content_summary"] = _build_content_summary_from_yields(realized_yields)
    rebased["sample_mining_session"] = [*prefix, *generated_phase, *generated_trailing_block, *generated_suffix]
    return rebased


def load_test_journal_events(*, rebase_to_now: bool = True, system_name: str | None = None) -> dict[str, Any]:
    journal_path = TESTS_ROOT / "config" / "journal_events.json"
    payload = json.loads(journal_path.read_text(encoding="utf-8"))
    profile = load_generated_platinum_session_profile()
    payload = _apply_generated_platinum_profile(payload, profile)
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
