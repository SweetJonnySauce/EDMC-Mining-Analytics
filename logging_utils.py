"""Helper utilities to integrate with EDMC's logging system."""

from __future__ import annotations

import logging
from pathlib import Path

PLUGIN_FOLDER_NAME = Path(__file__).resolve().parent.name

try:  # pragma: no cover - only available when running inside EDMC
    from EDMCLogging import get_plugin_logger  # type: ignore[import]
except ImportError:  # pragma: no cover
    get_plugin_logger = None  # type: ignore[assignment]

if get_plugin_logger is not None:
    BASE_LOGGER = get_plugin_logger(PLUGIN_FOLDER_NAME)
else:
    BASE_LOGGER = logging.getLogger(PLUGIN_FOLDER_NAME)
    BASE_LOGGER.propagate = True


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return the shared plugin logger or one of its children."""

    if suffix is None:
        return BASE_LOGGER
    logger = BASE_LOGGER.getChild(suffix)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
    return logger


def set_log_level(level: int) -> None:
    """Update the base logger level (and implicitly its children)."""

    BASE_LOGGER.setLevel(level)
