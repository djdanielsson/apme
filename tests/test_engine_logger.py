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

    root = logging.getLogger()
    saved_root_handlers = root.handlers[:]
    root.handlers.clear()
    try:
        result = logger_mod.set_logger_channel("test.idempotent")
        assert result is True

        stdlib_logger = logging.getLogger("test.idempotent")
        handler_count = len(stdlib_logger.handlers)

        result = logger_mod.set_logger_channel("test.idempotent")
        assert result is False
        assert len(stdlib_logger.handlers) == handler_count
    finally:
        logging.getLogger("test.idempotent").handlers.clear()
        logging.getLogger("test.idempotent").propagate = True
        root.handlers = saved_root_handlers


def test_preconfigured_logger_preserved() -> None:
    """When the stdlib logger already has handlers, set_logger_channel is a no-op."""
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)

    channel = "test.preconfigured"
    stdlib_logger = logging.getLogger(channel)
    saved_level = stdlib_logger.level
    saved_propagate = stdlib_logger.propagate
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
        stdlib_logger.setLevel(saved_level)
        stdlib_logger.propagate = saved_propagate


def test_ancestor_handler_prevents_handler_installation() -> None:
    """When a root/ancestor logger has handlers, set_logger_channel skips installation.

    Regression test: hasHandlers() walks up the logger hierarchy, so a root
    logger configured via basicConfig()/dictConfig() prevents duplicate handler
    installation even when the named logger itself has no direct handlers.
    """
    import apme_engine.engine.logger as logger_mod

    importlib.reload(logger_mod)

    channel = "test.ancestor.child"
    stdlib_logger = logging.getLogger(channel)
    saved_handlers = stdlib_logger.handlers[:]
    saved_propagate = stdlib_logger.propagate
    stdlib_logger.handlers.clear()
    stdlib_logger.propagate = True

    root = logging.getLogger()
    saved_root_handlers = root.handlers[:]
    root_handler = logging.StreamHandler(sys.stderr)
    root.addHandler(root_handler)

    try:
        assert stdlib_logger.hasHandlers() is True
        assert len(stdlib_logger.handlers) == 0

        result = logger_mod.set_logger_channel(channel)
        assert result is False
        assert len(stdlib_logger.handlers) == 0
    finally:
        root.removeHandler(root_handler)
        root.handlers = saved_root_handlers
        stdlib_logger.handlers = saved_handlers
        stdlib_logger.propagate = saved_propagate
