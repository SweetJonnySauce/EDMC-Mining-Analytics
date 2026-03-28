"""Shared helpers for browser capability providers."""

from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
from urllib.parse import urlparse
import webbrowser
from typing import Iterable, Mapping, Sequence

from ...logging_utils import get_logger

_log = get_logger("capabilities.browser")

_BROWSER_CLASS_HINTS = (
    "firefox",
    "google-chrome",
    "chromium",
    "brave-browser",
    "microsoft-edge",
    "vivaldi",
)


@dataclass(frozen=True)
class BrowserWindowInfo:
    window_id: str
    window_class: str
    title: str


def open_browser_url(url: str, *, prefer_foreground: bool = True) -> bool:
    """Open browser URL with best-effort foreground hint."""

    target = str(url or "").strip()
    if not target:
        return False

    attempts: tuple[tuple[int, bool], ...]
    if prefer_foreground:
        attempts = ((0, True), (1, True), (2, True))
    else:
        attempts = ((2, False),)

    for new_value, autoraise in attempts:
        try:
            if webbrowser.open(target, new=new_value, autoraise=autoraise):
                return True
        except Exception:
            continue
    return False


def try_raise_browser_x11(
    *,
    timeout_seconds: float,
    has_wmctrl: bool,
    has_xdotool: bool,
    target_url: str = "",
    title_hints: Sequence[str] = (),
    preexisting_window_titles: Mapping[str, str] | None = None,
) -> bool:
    """Try to activate an existing browser window on X11."""

    timeout = max(0.1, float(timeout_seconds))

    if has_wmctrl and _raise_with_wmctrl(
        timeout=timeout,
        target_url=target_url,
        title_hints=title_hints,
        preexisting_window_titles=preexisting_window_titles or {},
    ):
        return True
    if has_xdotool and _raise_with_xdotool(timeout=timeout, target_url=target_url, title_hints=title_hints):
        return True
    return False


def list_browser_windows(*, timeout: float) -> list[BrowserWindowInfo]:
    """Return visible browser windows from wmctrl output."""

    try:
        output = subprocess.check_output(
            ["wmctrl", "-lx"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except Exception:
        return []

    windows: list[BrowserWindowInfo] = []
    for line in output.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 3:
            continue
        window_id = parts[0]
        window_class = parts[2].lower()
        if not any(hint in window_class for hint in _BROWSER_CLASS_HINTS):
            continue
        title = parts[4] if len(parts) >= 5 else ""
        windows.append(BrowserWindowInfo(window_id=window_id, window_class=window_class, title=title))
    return windows


def select_browser_window_id(
    windows: Sequence[BrowserWindowInfo],
    *,
    target_url: str = "",
    title_hints: Sequence[str] = (),
    preexisting_window_titles: Mapping[str, str] | None = None,
) -> str | None:
    """Select the most likely browser window for the target page."""

    if not windows:
        return None

    normalized_hints: list[str] = []
    for hint in title_hints:
        text = str(hint or "").strip().lower()
        if text:
            normalized_hints.append(text)
    parsed = urlparse(str(target_url or "").strip())
    if parsed.netloc:
        normalized_hints.append(parsed.netloc.lower())
    if parsed.path:
        normalized_hints.append(parsed.path.lower())

    preexisting = dict(preexisting_window_titles or {})
    scored: list[tuple[int, BrowserWindowInfo]] = []
    for window in windows:
        score = 0
        title = window.title.lower()
        preexisting_title = preexisting.get(window.window_id, "")
        preexisting_title_lower = preexisting_title.lower()
        is_new_window = window.window_id not in preexisting
        title_changed = bool(preexisting_title) and (preexisting_title != window.title)
        matches_hint_now = bool(normalized_hints) and any(hint in title for hint in normalized_hints)
        matched_hint_before = bool(normalized_hints) and any(
            hint in preexisting_title_lower for hint in normalized_hints
        )

        if is_new_window:
            score += 500
        if matches_hint_now and not matched_hint_before:
            score += 350
        if matches_hint_now and title_changed:
            score += 250
        if title_changed:
            score += 100
        if matches_hint_now:
            score += 50
        if matches_hint_now and matched_hint_before and not title_changed:
            score -= 100
        scored.append((score, window))

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_window = scored[0]
    if best_score <= 0:
        return None
    return best_window.window_id


def _raise_with_wmctrl(
    *,
    timeout: float,
    target_url: str,
    title_hints: Sequence[str],
    preexisting_window_titles: Mapping[str, str],
) -> bool:
    deadline = time.monotonic() + max(0.2, timeout)
    windows: list[BrowserWindowInfo] = []
    target_id: str | None = None

    # Poll briefly so we can catch title updates/new windows caused by the open action.
    while time.monotonic() < deadline:
        windows = list_browser_windows(timeout=timeout)
        if not windows:
            time.sleep(0.05)
            continue
        target_id = select_browser_window_id(
            windows,
            target_url=target_url,
            title_hints=title_hints,
            preexisting_window_titles=preexisting_window_titles,
        )
        if target_id:
            break
        time.sleep(0.05)

    if not windows:
        return False

    ordered_ids: list[str] = []
    if target_id:
        ordered_ids.append(target_id)
    ordered_ids.extend(window.window_id for window in windows if window.window_id != target_id)

    for window_id in ordered_ids:
        try:
            proc = subprocess.run(
                ["wmctrl", "-ia", window_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            _log.debug("Raised browser window using wmctrl window_id=%s", window_id)
            return True
    return False


def _raise_with_xdotool(*, timeout: float, target_url: str, title_hints: Sequence[str]) -> bool:
    parsed = urlparse(str(target_url or "").strip())
    name_hints: list[str] = []
    for hint in title_hints:
        text = str(hint or "").strip()
        if text:
            name_hints.append(text)
    if parsed.netloc:
        name_hints.append(parsed.netloc)

    for hint in name_hints:
        try:
            proc = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", hint, "windowactivate"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            _log.debug("Raised browser window using xdotool title hint=%s", hint)
            return True

    for hint in _BROWSER_CLASS_HINTS:
        try:
            proc = subprocess.run(
                [
                    "xdotool",
                    "search",
                    "--onlyvisible",
                    "--class",
                    hint,
                    "windowactivate",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except Exception:
            continue
        if proc.returncode == 0:
            _log.debug("Raised browser window using xdotool class=%s", hint)
            return True
    return False


def browser_tool_metadata(*, has_wmctrl: bool, has_xdotool: bool) -> dict[str, bool]:
    return {
        "has_wmctrl": bool(has_wmctrl),
        "has_xdotool": bool(has_xdotool),
    }


def safe_bool(value: object) -> bool:
    return bool(value)


def iter_class_hints() -> Iterable[str]:
    return _BROWSER_CLASS_HINTS
