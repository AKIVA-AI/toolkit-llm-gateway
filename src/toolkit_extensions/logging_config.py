"""
Toolkit LLM Gateway - Structured Logging Configuration

Provides a JSON logging formatter and setup function for
structured, machine-parseable log output.
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional


class StructuredJsonFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects.

    Each log line includes: timestamp, level, logger, message,
    and optional extras (exc_info, module, funcName, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Include any extra fields passed via `extra=` kwarg
        for key in ("request_id", "user_id", "team_id", "model", "provider", "cost"):
            value = getattr(record, key, None)
            if value is not None:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def configure_logging(
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
) -> None:
    """
    Configure logging for the toolkit_extensions package.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
               Defaults to LOG_LEVEL env var or INFO.
        json_format: If True, use structured JSON formatting.
                     Defaults to LOG_FORMAT=json env var.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    if json_format is None:
        json_format = os.getenv("LOG_FORMAT", "").lower() == "json"

    root_logger = logging.getLogger("toolkit_extensions")
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)

    if json_format:
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)
