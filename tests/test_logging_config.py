"""
Tests for structured JSON logging configuration
"""

import json
import logging
import os

import pytest

from toolkit_extensions.logging_config import (
    StructuredJsonFormatter,
    configure_logging,
)


def test_json_formatter_basic():
    """Test that JSON formatter produces valid JSON."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Hello %s",
        args=("world",),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "Hello world"
    assert parsed["line"] == 42
    assert "timestamp" in parsed


def test_json_formatter_with_exception():
    """Test that JSON formatter includes exception info."""
    formatter = StructuredJsonFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Something failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    parsed = json.loads(output)

    assert "exception" in parsed
    assert parsed["exception"]["type"] == "ValueError"
    assert "test error" in parsed["exception"]["message"]
    assert isinstance(parsed["exception"]["traceback"], list)


def test_json_formatter_with_extras():
    """Test that JSON formatter captures extra fields."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="request tracked",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.model = "gpt-4"
    record.cost = 0.05

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["request_id"] == "req-123"
    assert parsed["model"] == "gpt-4"
    assert parsed["cost"] == 0.05


def test_configure_logging_json(monkeypatch):
    """Test configure_logging with JSON format."""
    configure_logging(level="DEBUG", json_format=True)

    logger = logging.getLogger("toolkit_extensions")
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0].formatter, StructuredJsonFormatter)


def test_configure_logging_plain():
    """Test configure_logging with plain format."""
    configure_logging(level="WARNING", json_format=False)

    logger = logging.getLogger("toolkit_extensions")
    assert logger.level == logging.WARNING
    assert len(logger.handlers) == 1
    assert not isinstance(logger.handlers[0].formatter, StructuredJsonFormatter)


def test_configure_logging_from_env(monkeypatch):
    """Test that configure_logging reads from environment."""
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    monkeypatch.setenv("LOG_FORMAT", "json")

    configure_logging()

    logger = logging.getLogger("toolkit_extensions")
    assert logger.level == logging.ERROR
    assert isinstance(logger.handlers[0].formatter, StructuredJsonFormatter)
