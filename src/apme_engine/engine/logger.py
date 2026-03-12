from __future__ import annotations

import logging
import sys
from typing import Any

_logger: logging.Logger | None = None

log_level_map = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def set_logger_channel(channel: str = "") -> None:
    global _logger
    _logger = logging.getLogger(channel)
    handler = logging.StreamHandler(sys.stdout)
    # default formatter
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


def set_log_level(level_str: str = "info") -> None:
    global _logger
    level = log_level_map.get(level_str.lower())
    if _logger is not None and level is not None:
        _logger.setLevel(level)


def exception(*args: object, **kwargs: Any) -> None:
    if _logger is not None:
        _logger.exception(*args, **kwargs)


def error(*args: object, **kwargs: Any) -> None:
    if _logger is not None:
        _logger.error(*args, **kwargs)


def warning(*args: object, **kwargs: Any) -> None:
    if _logger is not None:
        _logger.warning(*args, **kwargs)


def info(*args: object, **kwargs: Any) -> None:
    if _logger is not None:
        _logger.info(*args, **kwargs)


def debug(*args: object, **kwargs: Any) -> None:
    if _logger is not None:
        _logger.debug(*args, **kwargs)
