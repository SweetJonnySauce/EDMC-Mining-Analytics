"""Helpers for building and launching Inara commodity searches."""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import Dict, Optional

from urllib.parse import urlencode

from ..state import MiningState
from ..logging_utils import get_logger


_log = get_logger("inara")


class InaraClient:
    """Encapsulates Inara commodity search URL generation and settings."""

    def __init__(self, state: MiningState) -> None:
        self._state = state
        self._commodity_map: Dict[str, int] = {}

    @property
    def commodity_map(self) -> Dict[str, int]:
        return self._commodity_map

    def load_mapping(self, path: Path) -> None:
        if not path.exists():
            _log.debug("Commodity link mapping file not found at %s", path)
            self._commodity_map = {}
            return

        try:
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except Exception:
            _log.exception("Failed to load commodity link mapping from %s", path)
            self._commodity_map = {}
            return

        if not isinstance(raw, dict):
            _log.warning("Commodity link mapping file is not a JSON object: %s", path)
            self._commodity_map = {}
            return

        processed: Dict[str, int] = {}
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            try:
                processed[key.strip().lower()] = int(value)
            except (TypeError, ValueError):
                _log.debug("Skipping commodity mapping with non-int value: %s=%r", key, value)

        self._commodity_map = processed

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------
    def build_url(self, commodity: str) -> Optional[str]:
        commodity_id = self._commodity_map.get(commodity.lower())
        if commodity_id is None:
            return None

        system_name = self._state.current_system
        if not system_name:
            _log.debug("Cannot build Inara link for %s: system unknown", commodity)
            return None

        include_carriers = "0" if self._state.market_search_include_carriers else "1"
        include_surface = "0" if self._state.market_search_include_surface else "1"
        sort_mode = (self._state.market_search_sort_mode or "best_price").strip().lower()
        search_mode = "3" if sort_mode == "nearest" else "1"

        query: Dict[str, object] = {
            "formbrief": "1",
            "pi1": "2",
            "pa1[]": [str(commodity_id)],
            "ps1": system_name,
            "pi10": search_mode,
            "pi4": include_surface,
            "pi8": include_carriers,
            "pi13": "0",
            "pi12": "0",
            "pi14": "0",
            "ps3": "",
        }

        distance_ly = self._state.market_search_distance_ly
        if distance_ly and distance_ly > 0:
            query["pi11"] = str(int(distance_ly))

        if self._state.market_search_has_large_pad:
            query["pi3"] = "3"

        distance_ls = self._state.market_search_distance_ls
        if distance_ls and distance_ls > 0:
            query["pi9"] = str(int(distance_ls))

        min_demand = self._state.market_search_min_demand
        if min_demand and min_demand > 0:
            query["pi7"] = str(int(min_demand))

        age_days = self._state.market_search_age_days
        if age_days and age_days > 0:
            query["pi5"] = str(int(age_days) * 24)

        try:
            return "https://inara.cz/elite/commodities/?" + urlencode(query, doseq=True)
        except Exception:
            _log.exception("Failed to encode Inara URL for commodity %s", commodity)
            return None

    def open_link(self, commodity: str) -> None:
        url = self.build_url(commodity)
        if not url:
            return
        try:
            if not webbrowser.open(url, new=2):
                webbrowser.open(url)
        except Exception:
            _log.exception("Failed to open browser for commodity %s", commodity)
