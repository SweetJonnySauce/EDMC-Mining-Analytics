"""Helper utilities to integrate with EDMC's logging system."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
from types import TracebackType

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


class _MissingLogFieldsFilter(logging.Filter):
    """Backfill EDMC log fields expected by formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "osthreadid"):
            try:
                record.osthreadid = threading.get_native_id()
            except Exception:
                record.osthreadid = getattr(record, "thread", 0)
        if not hasattr(record, "qualname"):
            record.qualname = record.name
        return True


def _ensure_log_filter(logger: logging.Logger) -> None:
    if not any(isinstance(flt, _MissingLogFieldsFilter) for flt in logger.filters):
        logger.addFilter(_MissingLogFieldsFilter())


_ensure_log_filter(BASE_LOGGER)
_EXCEPTION_HOOKS_INSTALLED = False
_DEFAULT_THREAD_PREFIXES = (
    "edmcma",
    "edmc mining",
    "edmc-spansh",
    "edmcmining",
)


def get_logger(suffix: str | None = None) -> logging.Logger:
    """Return the shared plugin logger or one of its children."""

    if suffix is None:
        return BASE_LOGGER
    logger = BASE_LOGGER.getChild(suffix)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
    _ensure_log_filter(logger)
    return logger


def set_log_level(level: int) -> None:
    """Update the base logger level (and implicitly its children)."""

    BASE_LOGGER.setLevel(level)


def install_exception_logging(logger: logging.Logger | None = None) -> None:
    """Route unhandled plugin exceptions to the EDMC log."""

    global _EXCEPTION_HOOKS_INSTALLED
    if _EXCEPTION_HOOKS_INSTALLED:
        return

    target_logger = logger or BASE_LOGGER
    _ensure_log_filter(target_logger)

    def _traceback_mentions_plugin(tb: TracebackType | None) -> bool:
        while tb is not None:
            try:
                filename = tb.tb_frame.f_code.co_filename
            except Exception:
                filename = ""
            if PLUGIN_FOLDER_NAME in filename:
                return True
            tb = tb.tb_next
        return False

    thread_prefixes = _DEFAULT_THREAD_PREFIXES
    prior_thread_hook = getattr(threading, "excepthook", None)

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        thread_name = args.thread.name or ""
        normalized = thread_name.lower()
        should_log = any(normalized.startswith(prefix) for prefix in thread_prefixes)
        if not should_log:
            should_log = _traceback_mentions_plugin(args.exc_traceback)
        if should_log:
            target_logger.exception(
                "Unhandled exception in thread %s",
                thread_name or "<unnamed>",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        if callable(prior_thread_hook) and prior_thread_hook is not _thread_excepthook:
            prior_thread_hook(args)

    if callable(prior_thread_hook):
        threading.excepthook = _thread_excepthook

    prior_sys_hook = sys.excepthook

    def _sys_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if _traceback_mentions_plugin(exc_traceback):
            target_logger.exception(
                "Unhandled exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
        if callable(prior_sys_hook) and prior_sys_hook is not _sys_excepthook:
            prior_sys_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _sys_excepthook
    _EXCEPTION_HOOKS_INSTALLED = True
