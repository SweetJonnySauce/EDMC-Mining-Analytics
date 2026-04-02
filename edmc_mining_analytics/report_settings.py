"""Persistence helpers for web report settings."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .logging_utils import get_logger

try:  # pragma: no cover - only available inside EDMC
    from config import config as edmc_config  # type: ignore[import]
except ImportError:  # pragma: no cover - tests/offline
    edmc_config = None  # type: ignore[assignment]

_log = get_logger("report_settings")

INDEX_REPORT_SETTINGS_KEY = "edmc_mining_report_index_settings"
COMPARE_REPORT_SETTINGS_KEY = "edmc_mining_report_compare_settings"

DEFAULT_INDEX_SETTINGS = {
    "materialPercentShowOnlyCollected": False,
    "materialPercentShowGridlines": True,
    "prospectFrequencyIncludeDuplicates": True,
    "prospectFrequencyBinSize": 5,
    "prospectFrequencyReverseCumulative": False,
    "prospectFrequencyShowAverageReference": True,
    "selectedYieldPopulationMode": "all",
    "cumulativeRenderMode": "line",
    "cumulativeValueMode": "quantity",
}

DEFAULT_COMPARE_SETTINGS = {
    "selectedYieldPopulationMode": "all",
    "selectedReferenceCrosshairs": ["avg"],
    "compareShowGridlines": True,
    "compareNormalizeMetrics": False,
    "compareReverseCumulative": False,
    "compareShowHistogram": False,
    "compareSortMode": "avg_desc",
    "compareThemeId": "orange-dark",
}

ALLOWED_YIELD_MODES = {"all", "present"}
ALLOWED_REFERENCE_CROSSHAIRS = {"p90", "p75", "p50", "avg", "p25"}
ALLOWED_COMPARE_SORT_MODES = {
    "avg_desc",
    "avg_asc",
    "p50_desc",
    "p50_asc",
    "p90_desc",
    "p90_asc",
    "p75_desc",
    "p75_asc",
    "p25_desc",
    "p25_asc",
    "name_asc",
}
ALLOWED_THEME_IDS = {
    "blue-light",
    "blue-dark",
    "orange-dark",
    "green-light",
    "green-dark",
}
ALLOWED_CUMULATIVE_RENDER_MODES = {"line", "stacked-area"}
ALLOWED_CUMULATIVE_VALUE_MODES = {"quantity", "profit"}


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "yes", "on"):
        return True
    if value in (0, "0", "false", "False", "no", "off"):
        return False
    return fallback


def _coerce_bin_size(value: Any, fallback: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return 10 if numeric == 10 else 5


def _coerce_choice(value: Any, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip().lower()
    if text in allowed:
        return text
    return fallback


def _coerce_reference_crosshairs(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        candidates = [str(entry or "").strip().lower() for entry in value]
    else:
        candidates = []
    sanitized: list[str] = []
    for entry in candidates:
        if entry in ALLOWED_REFERENCE_CROSSHAIRS and entry not in sanitized:
            sanitized.append(entry)
    if not sanitized:
        return list(fallback)
    return sanitized


def _read_json_config_dict(key: str) -> dict[str, Any]:
    if edmc_config is None:
        return {}
    try:
        raw = edmc_config.get_str(key=key)  # type: ignore[arg-type]
    except Exception:
        _log.debug("Failed to read report settings key=%s", key, exc_info=True)
        return {}
    if raw is None:
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except Exception:
        _log.debug("Failed to parse report settings JSON for key=%s", key, exc_info=True)
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _persist_json_config_dict(key: str, payload: dict[str, Any]) -> None:
    if edmc_config is None:
        return
    try:
        encoded = json.dumps(payload, separators=(",", ":"))
        edmc_config.set(key, encoded)
    except Exception:
        _log.exception("Failed to persist report settings key=%s", key)


def sanitize_index_report_settings(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    fallback = DEFAULT_INDEX_SETTINGS
    return {
        "materialPercentShowOnlyCollected": _coerce_bool(
            source.get("materialPercentShowOnlyCollected"),
            fallback["materialPercentShowOnlyCollected"],
        ),
        "materialPercentShowGridlines": _coerce_bool(
            source.get("materialPercentShowGridlines"),
            fallback["materialPercentShowGridlines"],
        ),
        "prospectFrequencyIncludeDuplicates": _coerce_bool(
            source.get("prospectFrequencyIncludeDuplicates"),
            fallback["prospectFrequencyIncludeDuplicates"],
        ),
        "prospectFrequencyBinSize": _coerce_bin_size(
            source.get("prospectFrequencyBinSize"),
            fallback["prospectFrequencyBinSize"],
        ),
        "prospectFrequencyReverseCumulative": _coerce_bool(
            source.get("prospectFrequencyReverseCumulative"),
            fallback["prospectFrequencyReverseCumulative"],
        ),
        "prospectFrequencyShowAverageReference": _coerce_bool(
            source.get("prospectFrequencyShowAverageReference"),
            fallback["prospectFrequencyShowAverageReference"],
        ),
        "selectedYieldPopulationMode": _coerce_choice(
            source.get("selectedYieldPopulationMode"),
            ALLOWED_YIELD_MODES,
            fallback["selectedYieldPopulationMode"],
        ),
        "cumulativeRenderMode": _coerce_choice(
            source.get("cumulativeRenderMode"),
            ALLOWED_CUMULATIVE_RENDER_MODES,
            fallback["cumulativeRenderMode"],
        ),
        "cumulativeValueMode": _coerce_choice(
            source.get("cumulativeValueMode"),
            ALLOWED_CUMULATIVE_VALUE_MODES,
            fallback["cumulativeValueMode"],
        ),
    }


def sanitize_compare_report_settings(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    fallback = DEFAULT_COMPARE_SETTINGS
    return {
        "selectedYieldPopulationMode": _coerce_choice(
            source.get("selectedYieldPopulationMode"),
            ALLOWED_YIELD_MODES,
            fallback["selectedYieldPopulationMode"],
        ),
        "selectedReferenceCrosshairs": _coerce_reference_crosshairs(
            source.get("selectedReferenceCrosshairs"),
            list(fallback["selectedReferenceCrosshairs"]),
        ),
        "compareShowGridlines": _coerce_bool(
            source.get("compareShowGridlines"),
            fallback["compareShowGridlines"],
        ),
        "compareNormalizeMetrics": _coerce_bool(
            source.get("compareNormalizeMetrics"),
            fallback["compareNormalizeMetrics"],
        ),
        "compareReverseCumulative": _coerce_bool(
            source.get("compareReverseCumulative"),
            fallback["compareReverseCumulative"],
        ),
        "compareShowHistogram": _coerce_bool(
            source.get("compareShowHistogram"),
            fallback["compareShowHistogram"],
        ),
        "compareSortMode": _coerce_choice(
            source.get("compareSortMode"),
            ALLOWED_COMPARE_SORT_MODES,
            fallback["compareSortMode"],
        ),
        "compareThemeId": _coerce_choice(
            source.get("compareThemeId"),
            ALLOWED_THEME_IDS,
            fallback["compareThemeId"],
        ),
    }


def load_report_settings() -> dict[str, dict[str, Any]]:
    index_settings = sanitize_index_report_settings(_read_json_config_dict(INDEX_REPORT_SETTINGS_KEY))
    compare_settings = sanitize_compare_report_settings(_read_json_config_dict(COMPARE_REPORT_SETTINGS_KEY))
    return {
        "index": index_settings,
        "compare": compare_settings,
    }


def save_report_settings(update_payload: Any) -> dict[str, dict[str, Any]]:
    current = load_report_settings()
    payload = update_payload if isinstance(update_payload, Mapping) else {}
    index_update = payload.get("index")
    compare_update = payload.get("compare")

    next_index = current["index"]
    if isinstance(index_update, Mapping):
        next_index = sanitize_index_report_settings(index_update)

    next_compare = current["compare"]
    if isinstance(compare_update, Mapping):
        next_compare = sanitize_compare_report_settings(compare_update)

    _persist_json_config_dict(INDEX_REPORT_SETTINGS_KEY, next_index)
    _persist_json_config_dict(COMPARE_REPORT_SETTINGS_KEY, next_compare)

    return {
        "index": next_index,
        "compare": next_compare,
    }
