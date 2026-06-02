"""Tests for apme_engine.engine.logger — no import-time side effects."""

from __future__ import annotations

import importlib
import logging
import sys


def test_no_import_time_logger_setup() -> None:
    """Importing scanner does not configure the module logger."""
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)
    assert not logger_mod.is_configured()

    sys.modules.pop("apme_engine.engine.scanner", None)
    importlib.import_module("apme_engine.engine.scanner")

    assert not logger_mod.is_configured()


def test_set_logger_channel_idempotent() -> None:
    """Calling set_logger_channel multiple times does not add duplicate handlers."""
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)

    result = logger_mod.set_logger_channel("test.idempotent")
    assert result is True

    stdlib_logger = logging.getLogger("test.idempotent")
    handler_count = len(stdlib_logger.handlers)

    result = logger_mod.set_logger_channel("test.idempotent")
    assert result is False
    assert len(stdlib_logger.handlers) == handler_count


def test_preconfigured_logger_preserved() -> None:
    """When the stdlib logger already has handlers, set_logger_channel is a no-op."""
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)

    channel = "test.preconfigured"
    stdlib_logger = logging.getLogger(channel)
    existing_handler = logging.StreamHandler(sys.stderr)
    stdlib_logger.addHandler(existing_handler)
    stdlib_logger.setLevel(logging.DEBUG)

    try:
        result = logger_mod.set_logger_channel(channel)
        assert result is False
        assert len(stdlib_logger.handlers) == 1
        assert stdlib_logger.handlers[0] is existing_handler
        assert stdlib_logger.level == logging.DEBUG
    finally:
        stdlib_logger.removeHandler(existing_handler)
