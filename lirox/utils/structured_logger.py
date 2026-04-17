"""
Lirox v1.1 — Structured Logging System [FIX #3]

Implements JSON-structured logging for debugging, auditing, and analysis.
All logs include: timestamp, level, component, message, metadata.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """Formats logs as JSON with metadata."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Include extra metadata if present
        if hasattr(record, 'metadata'):
            log_data.update(record.metadata)
        
        return json.dumps(log_data)


import threading
_logger_lock = threading.Lock()

def get_logger(name: str) -> logging.Logger:
    """Get a structured logger instance. Thread-safe handler setup."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        with _logger_lock:
            # Re-check inside the lock (double-checked locking)
            if not logger.handlers:
                from lirox.config import DATA_DIR
                import os
                log_path = os.path.join(DATA_DIR, "agent.log")
                handler = logging.FileHandler(log_path)
                handler.setFormatter(StructuredFormatter())
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
    return logger


def log_with_metadata(
    logger: logging.Logger,
    level: str,
    message: str,
    **metadata: Any
) -> None:
    """
    Log with structured metadata.
    
    Example:
        log_with_metadata(
            logger, "INFO", "Tool executed",
            tool="browser", url="https://example.com", duration_ms=1200
        )
    """
    record = logging.LogRecord(
        name=logger.name,
        level=getattr(logging, level.upper()),
        pathname="", lineno=0, msg=message,
        args=(), exc_info=None
    )
    record.metadata = metadata
    logger.handle(record)
