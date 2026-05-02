"""
Structured logging for the Ambulance Optimizer.

Every log entry is a JSON object with consistent fields:
    timestamp, level, logger, message, + any extra context passed in.

Usage:
    from core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Dispatch completed", incident_id=inc_id, unit_id=unit, eta=eta)
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any
from backend.core.config import settings


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach any extra fields passed as keyword args
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log_obj[key] = value

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable format for local development."""
    FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DATE_FMT = "%H:%M:%S"

    def __init__(self):
        super().__init__(fmt=self.FMT, datefmt=self.DATE_FMT)


def setup_logging() -> None:
    """Configure root logger. Called once at application startup."""
    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Always use __name__ as the name."""
    return logging.getLogger(name)
