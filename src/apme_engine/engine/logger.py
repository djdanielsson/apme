"""Logging configuration and convenience functions for the engine."""

from __future__ import annotations

import logging
import sys

_logger: logging.Logger | None = None

log_level_map = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def set_logger_channel(channel: str = "") -> None:
    """Configure the module logger with a channel name and stdout handler.

    Idempotent: if the logger has already been configured, subsequent calls
    are no-ops (the channel, handler, and formatter are unchanged).

    Args:
        channel: Logger name (e.g. module path). Empty for root logger.
    """
    global _logger
    if _logger is not None:
        return
    _logger = logging.getLogger(channel)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


def is_configured() -> bool:
    """Return whether the module logger has been initialized.

    Returns:
        True if the logger has been set up via set_logger_channel().
    """
    return _logger is not None


def set_log_level(level_str: str = "info") -> None:
    """Set the log level for the module logger.

    Args:
        level_str: Level name: "error", "warning", "info", or "debug".
    """
    global _logger
    level = log_level_map.get(level_str.lower())
    if _logger is not None and level is not None:
        _logger.setLevel(level)


def exception(*args: object, **kwargs: object) -> None:
    """Log an exception with traceback. No-op if logger not configured.

    Args:
        *args: Positional args passed to logger.exception.
        **kwargs: Keyword args passed to logger.exception.
    """
    if _logger is not None:
        _logger.exception(*args, **kwargs)  # type: ignore[arg-type]


def error(*args: object, **kwargs: object) -> None:
    """Log an error message. No-op if logger not configured.

    Args:
        *args: Positional args passed to logger.error.
        **kwargs: Keyword args passed to logger.error.
    """
    if _logger is not None:
        _logger.error(*args, **kwargs)  # type: ignore[arg-type]


def warning(*args: object, **kwargs: object) -> None:
    """Log a warning message. No-op if logger not configured.

    Args:
        *args: Positional args passed to logger.warning.
        **kwargs: Keyword args passed to logger.warning.
    """
    if _logger is not None:
        _logger.warning(*args, **kwargs)  # type: ignore[arg-type]


def info(*args: object, **kwargs: object) -> None:
    """Log an info message. No-op if logger not configured.

    Args:
        *args: Positional args passed to logger.info.
        **kwargs: Keyword args passed to logger.info.
    """
    if _logger is not None:
        _logger.info(*args, **kwargs)  # type: ignore[arg-type]


def debug(*args: object, **kwargs: object) -> None:
    """Log a debug message. No-op if logger not configured.

    Args:
        *args: Positional args passed to logger.debug.
        **kwargs: Keyword args passed to logger.debug.
    """
    if _logger is not None:
        _logger.debug(*args, **kwargs)  # type: ignore[arg-type]
