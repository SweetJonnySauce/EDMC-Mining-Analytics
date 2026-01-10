"""EDMC Mining Analytics plugin package."""

from __future__ import annotations

from .edmc_mining_analytics_version import PLUGIN_VERSION, VERSION, __version__
from .plugin import MiningAnalyticsPlugin

__all__ = ["MiningAnalyticsPlugin", "PLUGIN_VERSION", "VERSION", "__version__"]
