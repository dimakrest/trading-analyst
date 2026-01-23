"""Structured logging utilities for performance metrics.

This module configures structlog for structured logging with performance metrics.
Uses JSON format for easy parsing and analysis.
"""
import logging
import sys

import structlog


def configure_structured_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Sets up structlog with:
    - JSON formatting for production
    - Console formatting for development
    - Timestamp inclusion
    - Log level filtering

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        BoundLogger instance for structured logging
    """
    return structlog.get_logger(name)
