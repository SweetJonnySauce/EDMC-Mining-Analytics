"""Runtime environment probes used by capability resolver/provider selection."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Snapshot of runtime environment features relevant to capability resolution."""

    platform: str
    wayland_display: bool
    x11_display: bool
    has_wmctrl: bool
    has_xdotool: bool

    @property
    def is_windows(self) -> bool:
        return self.platform.startswith("win")

    @property
    def is_linux(self) -> bool:
        return self.platform.startswith("linux")


def detect_environment() -> EnvironmentSnapshot:
    """Collect runtime environment indicators for resolver decisions."""

    return EnvironmentSnapshot(
        platform=sys.platform,
        wayland_display=bool(os.environ.get("WAYLAND_DISPLAY")),
        x11_display=bool(os.environ.get("DISPLAY")),
        has_wmctrl=shutil.which("wmctrl") is not None,
        has_xdotool=shutil.which("xdotool") is not None,
    )
