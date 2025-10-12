"""Auto-update helper for the EDMC Mining Analytics plugin."""

from __future__ import annotations

import errno
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zipfile import ZIP_DEFLATED, ZipFile

import requests

from logging_utils import get_logger
from edmc_mining_analytics_version import PLUGIN_VERSION, is_newer_version

BACKUP_COUNT = 3
DATETIME_FORMAT = "%Y-%m-%d-%H-%M-%S"
DISABLE_FILE = "disable-auto-update.txt"
DOWNLOAD_FILENAME = "latest.zip"
RELEASES_URL = "https://api.github.com/repos/SweetJonnySauce/EDMC-Mining-Analytics/releases/latest"
PACKAGE_ROOT_NAME = "EDMC-Mining-Analytics"


class UpdateManager:
    """Handles automatic update checks and installation."""

    def __init__(
        self,
        plugin_dir: Path,
        on_update_ready: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._log = get_logger("update")
        self._plugin_dir = plugin_dir
        self._updates_dir = self._plugin_dir / "updates"
        self._backups_dir = self._plugin_dir / "backups"
        self._download_path = self._updates_dir / DOWNLOAD_FILENAME
        self._thread: Optional[threading.Thread] = None
        self._on_update_ready = on_update_ready

    def start(self) -> None:
        """Kick off the update check on a background thread."""

        if not self._plugin_dir:
            return

        if (self._plugin_dir / DISABLE_FILE).exists():
            self._log.info("Auto-update disabled via %s", DISABLE_FILE)
            return

        try:
            self._updates_dir.mkdir(parents=True, exist_ok=True)
            self._backups_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                self._log.warning("Unable to prepare update folders", exc_info=exc)
                return

        self._thread = threading.Thread(target=self._run_update_check, name="EDMC Mining Auto Update", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_update_check(self) -> None:
        try:
            release = requests.get(RELEASES_URL, timeout=10)
            release.raise_for_status()
        except Exception as exc:
            self._log.debug("Unable to fetch release metadata: %s", exc)
            return

        data = release.json()
        tag = str(data.get("tag_name", "")).strip()
        if not tag:
            return

        remote_version = tag.lstrip("vV")
        if not is_newer_version(remote_version, PLUGIN_VERSION):
            if is_newer_version(PLUGIN_VERSION, remote_version):
                self._log.debug(
                    "Current version %s is ahead of GitHub release %s",
                    PLUGIN_VERSION,
                    remote_version,
                )
            else:
                self._log.debug("Current version %s is up to date", PLUGIN_VERSION)
            return

        assets = data.get("assets") or []
        download_url = None
        for asset in assets:
            url = asset.get("browser_download_url")
            if url:
                download_url = url
                break
        if not download_url:
            self._log.debug("No downloadable asset found in latest release")
            return

        self._log.info("New version %s available (current %s)", remote_version, PLUGIN_VERSION)

        if not self._download_asset(download_url):
            return

        if not self._create_backup():
            return

        self._prune_backups()
        if not self._install_update(remote_version):
            return

        if self._on_update_ready:
            try:
                self._on_update_ready(remote_version)
            except Exception:
                self._log.debug("Update ready callback failed", exc_info=True)

    def _download_asset(self, url: str) -> bool:
        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with self._download_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            handle.write(chunk)
        except Exception as exc:
            self._log.warning("Failed to download new release", exc_info=exc)
            return False
        return True

    def _create_backup(self) -> bool:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        backup_path = self._backups_dir / f"{timestamp}.zip"

        try:
            with ZipFile(backup_path, "w", compression=ZIP_DEFLATED) as archive:
                for path in self._plugin_dir.rglob("*"):
                    if path.is_dir():
                        continue
                    relative = path.relative_to(self._plugin_dir)
                    # Skip update artefacts and backups themselves
                    if relative.parts[0] in {"updates", "backups"}:
                        continue
                    if relative.name.startswith(".") or relative.suffix in {".pyc", ".pyo"}:
                        continue
                    archive.write(path, arcname=str(relative))
        except Exception as exc:
            self._log.warning("Failed to create backup", exc_info=exc)
            return False
        return True

    def _prune_backups(self) -> None:
        backups = sorted(self._backups_dir.glob("*.zip"), key=lambda p: p.stat().st_ctime)
        for old_backup in backups[:-BACKUP_COUNT]:
            try:
                old_backup.unlink()
            except Exception:
                self._log.debug("Unable to remove backup %s", old_backup, exc_info=True)

    def _install_update(self, remote_version: str) -> bool:
        if not self._download_path.exists():
            self._log.debug("Downloaded update archive missing")
            return False

        extract_root = self._updates_dir / "extracted"
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)

        try:
            with ZipFile(self._download_path, "r") as archive:
                archive.extractall(extract_root)
        except Exception as exc:
            self._log.warning("Failed to extract update archive", exc_info=exc)
            return False

        candidate = extract_root / PACKAGE_ROOT_NAME
        source_dir = candidate if candidate.exists() else extract_root

        for src in source_dir.rglob("*"):
            if src.is_dir():
                continue
            relative = src.relative_to(source_dir)
            target = self._plugin_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, target)
            except Exception as exc:
                self._log.warning("Failed to copy %s", relative, exc_info=exc)

        self._log.info(
            "Auto-update installed for version %s. Changes will take effect next restart.",
            remote_version,
        )
        return True
