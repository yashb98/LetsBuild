"""Tests for the LetsBuild structlog logging configuration."""

from __future__ import annotations

import structlog

import letsbuild.logging as lb_logging
from letsbuild.logging import configure_logging, get_logger


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def setup_method(self) -> None:
        """Reset the module-level _configured flag before each test."""
        lb_logging._configured = False

    def test_configure_logging_does_not_raise(self) -> None:
        """configure_logging() with defaults completes without error."""
        configure_logging()

    def test_configure_logging_json_output_does_not_raise(self) -> None:
        """configure_logging(json_output=True) completes without error."""
        configure_logging(json_output=True)

    def test_configure_logging_is_idempotent(self) -> None:
        """Multiple calls to configure_logging do not raise."""
        configure_logging()
        # Second call should be a no-op due to the _configured guard.
        configure_logging()
        # Third call with different args is still a no-op.
        configure_logging(json_output=True, level="DEBUG")

    def test_configured_flag_set_after_call(self) -> None:
        """The module _configured flag is True after configure_logging()."""
        assert lb_logging._configured is False
        configure_logging()
        assert lb_logging._configured is True


class TestGetLogger:
    """Tests for get_logger()."""

    def setup_method(self) -> None:
        """Reset the module-level _configured flag before each test."""
        lb_logging._configured = False

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_logger() returns a structlog bound logger instance."""
        logger = get_logger()
        # structlog.get_logger() returns a BoundLoggerLazyProxy which wraps BoundLogger
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "bind")

    def test_get_logger_with_name_returns_logger(self) -> None:
        """get_logger('test.module') returns a logger with standard methods."""
        logger = get_logger("test.module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")

    def test_get_logger_auto_configures(self) -> None:
        """get_logger() calls configure_logging() if not yet configured."""
        assert lb_logging._configured is False
        get_logger()
        assert lb_logging._configured is True

    def test_get_logger_with_initial_binds(self) -> None:
        """get_logger() accepts initial bind key-value pairs."""
        logger = get_logger("test.bound", thread_id="t-123", layer=1)
        assert isinstance(logger, structlog.stdlib.BoundLogger)
