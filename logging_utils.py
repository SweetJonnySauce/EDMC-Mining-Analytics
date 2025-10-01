"""Helper utilities to integrate with EDMC's logging system."""

from __future__ import annotations

import logging

PLUGIN_LOGGER_NAME = "EDMC Mining Analytics"

try:  # pragma: no cover - only available when running inside EDMC
    from EDMCLogging import get_plugin_logger  # type: ignore[import]
except ImportError:  # pragma: no cover
    get_plugin_logger = None  # type: ignore[assignment]

if get_plugin_logger is not None:
    BASE_LOGGER = get_plugin_logger(PLUGIN_LOGGER_NAME)
else:
    BASE_LOGGER = logging.getLogger(PLUGIN_LOGGER_NAME)
    BASE_LOGGER.propagate = True


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return the shared plugin logger or one of its children."""

    if suffix is None:
        return BASE_LOGGER
    name = f"{PLUGIN_LOGGER_NAME}.{suffix}"
    logger = logging.getLogger(name)
    logger.propagate = True
    logger.setLevel(BASE_LOGGER.level)
    return logger


def set_log_level(level: int) -> None:
    """Update the base logger level (and implicitly its children)."""

    BASE_LOGGER.setLevel(level)

