"""Capability providers."""

from .base import CapabilityProvider
from .browser_generic import BrowserGenericProvider
from .browser_linux_wayland import BrowserLinuxWaylandProvider
from .browser_linux_x11 import BrowserLinuxX11Provider
from .browser_windows import BrowserWindowsProvider

__all__ = [
    "CapabilityProvider",
    "BrowserGenericProvider",
    "BrowserLinuxWaylandProvider",
    "BrowserLinuxX11Provider",
    "BrowserWindowsProvider",
]
