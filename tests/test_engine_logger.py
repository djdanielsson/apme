"""Tests for apme_engine.engine.logger — no import-time side effects."""

from __future__ import annotations

import importlib
import sys


def test_no_import_time_logger_setup() -> None:
    """Importing scanner does not configure the module logger."""
    import apme_engine.engine.logger as logger_mod

    # Reset logger state to simulate a clean slate
    importlib.reload(logger_mod)
    assert logger_mod._logger is None

    # Evict scanner so the next import re-executes its module-level code
    sys.modules.pop("apme_engine.engine.scanner", None)
    import apme_engine.engine.scanner  # noqa: F401

    # Check _logger *without* reloading logger_mod — reload would reset it
    assert logger_mod._logger is None


def test_set_logger_channel_idempotent() -> None:
    """Calling set_logger_channel multiple times does not add duplicate handlers."""
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)

    logger_mod.set_logger_channel("test.channel")
    assert logger_mod._logger is not None
    handler_count = len(logger_mod._logger.handlers)

    # Second call should be a no-op
    logger_mod.set_logger_channel("test.channel")
    assert len(logger_mod._logger.handlers) == handler_count
