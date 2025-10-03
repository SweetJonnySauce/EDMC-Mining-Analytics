"""Core orchestration for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib import error, request

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - EDMC always provides tkinter
    raise RuntimeError("Tkinter must be available for EDMC plugins") from exc

try:
    import myNotebook as nb  # type: ignore[import]
except ImportError:  # pragma: no cover - EDMC loads this in production
    nb = None  # type: ignore[assignment]

try:
    from config import appname  # type: ignore[import]
except ImportError:  # pragma: no cover
    appname = "EDMarketConnector"  # type: ignore[assignment]

from integrations.mining_inara import InaraClient
from journal import JournalProcessor
from preferences import PreferencesManager
from session_recorder import SessionRecorder
from state import MiningState, reset_mining_state
from logging_utils import get_logger, set_log_level
from version import PLUGIN_VERSION, is_newer_version
from mining_analytics_ui import edmcmaMiningUI


PLUGIN_NAME = "EDMC Mining Analytics"
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/releases/latest"
)
GITHUB_TAGS_API = "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/tags?per_page=1"


def _coerce_log_level(value: object) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.isdigit():
            try:
                return int(candidate)
            except ValueError:
                return None
        upper = candidate.upper()
        return logging._nameToLevel.get(upper)  # type: ignore[attr-defined]
    return None


def _resolve_edmc_log_level() -> int:
    base_logger = logging.getLogger(appname) if appname else logging.getLogger()
    fallback = base_logger.getEffectiveLevel()
    try:
        from config import config  # type: ignore[import]
    except ImportError:
        config = None  # type: ignore[assignment]

    if config is None:
        return fallback

    candidates = ("loglevel", "log_level", "logging_level")
    getters = ("getint", "get", "get_str")

    for key in candidates:
        for getter_name in getters:
            getter = getattr(config, getter_name, None)
            if getter is None:
                continue
            try:
                raw_value = getter(key)
            except Exception:
                continue
            level = _coerce_log_level(raw_value)
            if level is not None:
                return level
    return fallback


set_log_level(_resolve_edmc_log_level())
_log = get_logger()


class MiningAnalyticsPlugin:
    """Coordinates state, UI, preferences, and journal processing."""

    def __init__(self) -> None:
        self.state = MiningState()
        self.preferences = PreferencesManager()
        self.inara = InaraClient(self.state)
        self.session_recorder = SessionRecorder(self.state)
        self.ui = edmcmaMiningUI(
            self.state,
            self.inara,
            self._handle_reset_request,
            on_pause_changed=self._handle_pause_change,
            on_reset_inferred_capacities=self._handle_reset_inferred_capacities,
            on_test_webhook=self._handle_test_webhook,
        )
        self.journal = JournalProcessor(
            self.state,
            refresh_ui=self._refresh_ui_safe,
            on_session_start=self._on_session_start,
            on_session_end=self._on_session_end,
            persist_inferred_capacities=self._persist_inferred_capacities,
            notify_mining_activity=self._handle_mining_activity,
            session_recorder=self.session_recorder,
        )

        self.plugin_dir: Optional[Path] = None
        self._latest_version: Optional[str] = None
        self._version_check_started = False

    # ------------------------------------------------------------------
    # EDMC lifecycle hooks
    # ------------------------------------------------------------------
    def plugin_start(self, plugin_dir: str) -> str:
        self.plugin_dir = Path(plugin_dir)
        self.state.plugin_dir = self.plugin_dir
        self._sync_logger_level()
        _log.info("Starting %s v%s", PLUGIN_NAME, PLUGIN_VERSION)
        self.preferences.load(self.state)
        self.inara.load_mapping(self.plugin_dir / "commodity_links.json")
        self._ensure_version_check()
        return PLUGIN_NAME

    def plugin_app(self, parent: tk.Widget) -> tk.Frame:
        frame = self.ui.build(parent)
        self._refresh_ui_safe()
        self.ui.schedule_rate_update()
        return frame

    def plugin_prefs(
        self,
        parent: tk.Widget,
        cmdr: Optional[str] = None,
        is_beta: bool = False,
    ) -> tk.Widget:
        if nb is not None:
            container: tk.Widget = nb.Frame(parent)
        else:
            container = ttk.Frame(parent)
        prefs = self.ui.build_preferences(container)
        prefs.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        if cmdr:
            self.state.cmdr_name = cmdr
        return container

    def plugin_stop(self) -> None:
        _log.info("Stopping %s", PLUGIN_NAME)
        self.ui.cancel_rate_update()
        self.ui.close_histogram_windows()
        reset_mining_state(self.state)
        self._refresh_ui_safe()

    def handle_journal_entry(
        self,
        entry: dict,
        shared_state: Optional[dict] = None,
        cmdr: Optional[str] = None,
    ) -> None:
        self._update_commander(entry, shared_state, cmdr)
        self.journal.handle_entry(entry, shared_state)

    def prefs_changed(self, cmdr: Optional[str], is_beta: bool) -> None:
        self._sync_logger_level()
        self.preferences.save(self.state)
        if cmdr:
            self.state.cmdr_name = cmdr

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _handle_reset_request(self) -> None:
        now = datetime.now(timezone.utc)
        state = self.state

        session_was_active = bool(state.mining_start or state.is_mining)
        if session_was_active:
            state.is_mining = False
            state.mining_end = now
            if self.session_recorder:
                try:
                    self.session_recorder.end_session(
                        now,
                        reason="manual reset",
                        reset=True,
                        force_summary=state.send_reset_summary,
                    )
                except Exception:
                    _log.exception("Failed to finalize mining session during reset")
            self._on_session_end()
        else:
            self.ui.cancel_rate_update()

        reset_mining_state(state)
        self.ui.clear_transient_widgets()
        self.ui.set_paused(False, source="system")
        self._refresh_ui_safe()

    def _refresh_ui_safe(self) -> None:
        try:
            self.ui.refresh()
        except Exception:
            _log.exception("Failed to refresh Mining Analytics UI")

    def _on_session_start(self) -> None:
        self.ui.schedule_rate_update()

    def _on_session_end(self) -> None:
        self.ui.cancel_rate_update()
        self._refresh_ui_safe()
        self._persist_inferred_capacities()

    def _sync_logger_level(self) -> None:
        try:
            set_log_level(_resolve_edmc_log_level())
        except Exception:
            pass

    def _persist_inferred_capacities(self) -> None:
        try:
            self.preferences.save_inferred_capacities(self.state)
        except Exception:
            _log.exception("Failed to persist inferred cargo capacities")

    def _handle_mining_activity(self, reason: str) -> None:
        if not self.state.auto_unpause_on_event or not self.state.is_paused:
            return
        _log.debug("Mining activity detected (%s); auto-resuming paused updates", reason)
        try:
            self.ui.set_paused(False, source="auto")
        except Exception:
            _log.exception("Failed to auto-resume after %s", reason)

    def _handle_pause_change(self, paused: bool, source: str, timestamp: datetime) -> None:
        try:
            self.session_recorder.record_pause(timestamp, paused=paused, source=source)
        except Exception:
            _log.exception("Failed to record pause state change")

    def _handle_reset_inferred_capacities(self) -> None:
        _log.info("Resetting inferred cargo capacities at user request")
        self.preferences.reset_inferred_capacities(self.state)
        if self.state.cargo_capacity_is_inferred:
            self.state.cargo_capacity = None
            self.state.cargo_capacity_is_inferred = False
        self._refresh_ui_safe()

    def _handle_test_webhook(self) -> None:
        try:
            _log.info("Dispatching Discord webhook test message")
            success, message = self.session_recorder.send_test_message()
            if success:
                _log.info("Discord webhook test message sent successfully")
            else:
                detail = f": {message}" if message else ""
                _log.warning(
                    "Discord webhook test message failed%s (see prior logs for details)",
                    detail,
                )
        except ValueError as exc:
            _log.warning("Discord webhook test skipped: %s", exc)
        except Exception:
            _log.exception("Failed to send Discord webhook test message")

    def _update_commander(
        self,
        entry: Optional[dict],
        shared_state: Optional[dict],
        cmdr: Optional[str],
    ) -> None:
        commander: Optional[str] = cmdr
        if isinstance(entry, dict):
            commander = commander or entry.get("Cmdr") or entry.get("Commander")
            if not commander:
                user = entry.get("UserName")
                if isinstance(user, str) and user.strip():
                    commander = user
        if not commander and isinstance(shared_state, dict):
            commander = shared_state.get("Cmdr") or shared_state.get("Commander")
        if commander:
            commander_str = str(commander).strip()
            if commander_str:
                self.state.cmdr_name = commander_str

    # ------------------------------------------------------------------
    # Version checking
    # ------------------------------------------------------------------
    def _ensure_version_check(self) -> None:
        if self._version_check_started:
            return
        self._version_check_started = True
        thread = threading.Thread(target=self._check_for_updates, name="EDMCMiningVersion", daemon=True)
        thread.start()

    def _fetch_latest_tag(self) -> Optional[str]:
        try:
            req = request.Request(
                GITHUB_TAGS_API,
                headers={"User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}"},
            )
            with request.urlopen(req, timeout=5) as response:
                payload = json.load(response)
        except error.URLError as exc:
            _log.debug("Tag lookup failed: %s", exc)
            return None
        except Exception:
            _log.exception("Unexpected error during tag lookup")
            return None

        if not isinstance(payload, list) or not payload:
            return None
        tag_payload = payload[0]
        tag = tag_payload.get("name") or tag_payload.get("ref")
        if isinstance(tag, str) and tag.startswith("refs/tags/"):
            tag = tag.split("/", 2)[-1]
        return tag if isinstance(tag, str) else None

    def _check_for_updates(self) -> None:
        try:
            req = request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}"},
            )
            with request.urlopen(req, timeout=5) as response:
                payload = json.load(response)
        except error.HTTPError as exc:
            if exc.code == 404:
                _log.debug("GitHub releases endpoint returned 404; falling back to tags")
                latest = self._fetch_latest_tag()
                if latest:
                    self._handle_latest_version(latest)
                else:
                    _log.debug("Version check fallback to tags did not return any versions")
                return
            _log.debug("Version check failed with HTTP status %s: %s", exc.code, exc)
            return
        except error.URLError as exc:
            _log.debug("Version check failed: %s", exc)
            return
        except Exception:
            _log.exception("Unexpected error during version check")
            return

        latest = payload.get("tag_name") or payload.get("name")
        if not latest:
            _log.debug("Version check succeeded but no tag information was found")
            return

        self._handle_latest_version(latest)

    def _log_version_status(self) -> None:
        if not self._latest_version:
            return
        if is_newer_version(self._latest_version, PLUGIN_VERSION):
            _log.info(
                "A newer version of %s is available: %s (current %s)",
                PLUGIN_NAME,
                self._latest_version,
                PLUGIN_VERSION,
            )
        else:
            _log.debug("%s is up to date (version %s)", PLUGIN_NAME, PLUGIN_VERSION)
        self._schedule_version_label_update()

    def _schedule_version_label_update(self) -> None:
        root = self.ui.get_root()
        if root and getattr(root, "after", None):
            root.after(
                0,
                lambda: self.ui.update_version_label(
                    PLUGIN_VERSION, self._latest_version
                ),
            )

    def _handle_latest_version(self, latest: str) -> None:
        self._latest_version = latest
        self._log_version_status()
