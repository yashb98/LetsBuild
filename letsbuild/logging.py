"""structlog configuration for LetsBuild.

Provides JSON (production) and console (dev) output modes with context binding
support for thread_id, layer, and agent. Call configure_logging() once at
application startup.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any

import structlog

_configured: bool = False
_configure_lock: threading.Lock = threading.Lock()


def configure_logging(
    json_output: bool = False,
    level: str = "INFO",
) -> None:
    """Configure structlog and stdlib logging for the entire application.

    Args:
        json_output: If True, render logs as JSON (production). Otherwise use
            the coloured console renderer (development).
        level: Root log level as a string (e.g. "DEBUG", "INFO", "WARNING").
    """
    global _configured

    with _configure_lock:
        if _configured:
            return

        log_level = getattr(logging, level.upper(), logging.INFO)

        # Shared processors used by both structlog and stdlib integration.
        shared_processors: list[structlog.types.Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.PATHNAME,
                ],
            ),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]

        if json_output:
            renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer()

        # Configure structlog itself.
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        # Configure stdlib logging so that libraries using stdlib also go
        # through structlog's formatting.
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
            foreign_pre_chain=shared_processors,
        )

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
        root_logger.setLevel(log_level)

        _configured = True


def get_logger(name: str | None = None, **initial_binds: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger, configuring logging if needed.

    Args:
        name: Logger name, typically the module path (e.g. "letsbuild.intake").
        **initial_binds: Initial context key-value pairs to bind to the logger.

    Returns:
        A BoundLogger instance with stdlib integration.
    """
    if not _configured:
        configure_logging()
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    if initial_binds:
        logger = logger.bind(**initial_binds)
    return logger
