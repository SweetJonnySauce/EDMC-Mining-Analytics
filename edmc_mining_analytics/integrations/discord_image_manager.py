"""Helpers for managing Discord embed images."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from ..state import MiningState


class DiscordImageManager:
    """Manage Discord image configuration stored on :class:`MiningState`."""

    _ANY_KEY = "__any__"

    def __init__(self, state: MiningState) -> None:
        self._state = state
        if getattr(state, "discord_images", None) is None:
            state.discord_images = []
        if getattr(state, "discord_image_cycle", None) is None:
            state.discord_image_cycle = {}

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list_images(self) -> List[tuple[str, str]]:
        """Return a copy of the configured ship/image pairs."""

        images = getattr(self._state, "discord_images", []) or []
        return [(ship or "", url) for ship, url in images if url]

    def select_image(self, ship_name: Optional[str]) -> Optional[str]:
        """Return the image URL for the given ship, rotating through matches."""

        entries = self.list_images()
        if not entries:
            return None

        ship = (ship_name or "").strip().lower()
        if not ship:
            ship = (self._state.current_ship or "").strip().lower()

        matches: List[str] = []
        any_matches: List[str] = []

        for raw_ship, raw_url in entries:
            url = raw_url.strip()
            if not url:
                continue
            ship_value = raw_ship.strip()
            if ship_value and ship_value.lower() != "any":
                if ship_value.lower() == ship:
                    matches.append(url)
            else:
                any_matches.append(url)

        image = self._cycle_choice(matches, ship if ship else self._ANY_KEY)
        if image:
            return image
        return self._cycle_choice(any_matches, self._ANY_KEY)

    # ------------------------------------------------------------------ #
    # Mutators
    # ------------------------------------------------------------------ #
    def add_image(self, ship: str, url: str) -> None:
        """Add a ship/image mapping and reset its rotation."""

        ship_value = ship.strip()
        if ship_value.lower() == "any":
            ship_value = ""
        url_value = url.strip()
        if not url_value:
            return

        images = getattr(self._state, "discord_images", [])
        images.append((ship_value, url_value))
        self._reset_cycle_for_keys((ship_value,))

    def remove_indices(self, indices: Iterable[int]) -> None:
        """Remove image entries at the given indices."""

        targets: List[int] = sorted(set(idx for idx in indices if isinstance(idx, int)), reverse=True)
        if not targets:
            return

        images = getattr(self._state, "discord_images", [])
        removed: List[str] = []
        for idx in targets:
            if 0 <= idx < len(images):
                ship_value, _ = images.pop(idx)
                ship_value = ship_value.strip()
                removed.append(ship_value if ship_value else "")
        self._reset_cycle_for_keys(removed)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _cycle_choice(self, urls: Sequence[str], key: str) -> Optional[str]:
        if not urls:
            return None
        cycle = getattr(self._state, "discord_image_cycle", None)
        if cycle is None:
            cycle = self._state.discord_image_cycle = {}
        idx = cycle.get(key, 0)
        selection = urls[idx % len(urls)]
        cycle[key] = (idx + 1) % len(urls)
        return selection

    def _reset_cycle_for_keys(self, ships: Iterable[str]) -> None:
        cycle = getattr(self._state, "discord_image_cycle", None)
        if cycle is None:
            cycle = self._state.discord_image_cycle = {}
        keys = set()
        for ship in ships:
            ship_value = (ship or "").strip()
            key = ship_value.lower() if ship_value and ship_value.lower() != "any" else self._ANY_KEY
            keys.add(key)

        images = getattr(self._state, "discord_images", [])
        for key in keys:
            cycle.pop(key, None)
