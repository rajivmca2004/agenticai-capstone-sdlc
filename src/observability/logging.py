# Copyright (c) Microsoft. All rights reserved.
"""
Logging and Observability Module

Provides:
- Structured JSON logging
- Correlation ID tracking
- Request/response logging
- Performance metrics
- Integration with LangSmith
"""

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Any, Callable

import structlog
from structlog.types import Processor

# =============================================================================
# CONTEXT VARIABLES
# =============================================================================

# Correlation ID for request tracking across services
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")

# Current operation context
operation_context_var: ContextVar[dict] = ContextVar("operation_context", default={})


# =============================================================================
# CORRELATION ID MANAGEMENT
# =============================================================================

def get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    cid = correlation_id_var.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_var.set(correlation_id)


def new_correlation_id() -> str:
    """Generate and set new correlation ID."""
    cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


# =============================================================================
# CUSTOM PROCESSORS
# =============================================================================

def add_correlation_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add correlation ID to log events."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def add_timestamp(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_service_info(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add service information to log events."""
    event_dict["service"] = "code-comprehension"
    event_dict["version"] = "0.2.0"
    return event_dict


def add_operation_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add operation context to log events."""
    ctx = operation_context_var.get()
    if ctx:
        event_dict.update(ctx)
    return event_dict


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format (True for production, False for development)
        log_file: Optional file path for log output
    """
    # Determine renderer based on format preference
    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    # Configure processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_timestamp,
        add_correlation_id,
        add_service_info,
        add_operation_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        renderer,
    ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# =============================================================================
# PERFORMANCE TRACKING
# =============================================================================

class PerformanceTracker:
    """Track performance metrics for operations."""
    
    def __init__(self, operation: str, logger: structlog.BoundLogger | None = None):
        self.operation = operation
        self.logger = logger or get_logger()
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.metadata: dict[str, Any] = {}
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        self.logger.info(
            "operation_started",
            operation=self.operation,
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type:
            self.logger.error(
                "operation_failed",
                operation=self.operation,
                duration_ms=round(duration_ms, 2),
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.metadata,
            )
        else:
            self.logger.info(
                "operation_completed",
                operation=self.operation,
                duration_ms=round(duration_ms, 2),
                **self.metadata,
            )
        
        return False  # Don't suppress exceptions
    
    def add_metadata(self, **kwargs):
        """Add metadata to be included in the completion log."""
        self.metadata.update(kwargs)


def track_performance(operation: str):
    """Decorator to track function performance."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            with PerformanceTracker(operation, logger) as tracker:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            with PerformanceTracker(operation, logger) as tracker:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# LOG CONTEXT MANAGER
# =============================================================================

class LogContext:
    """Context manager for adding temporary context to logs."""
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.token = None
    
    def __enter__(self):
        current = operation_context_var.get().copy()
        current.update(self.context)
        self.token = operation_context_var.set(current)
        return self
    
    def __exit__(self, *args):
        if self.token:
            operation_context_var.reset(self.token)


# =============================================================================
# METRICS COLLECTOR (Simple in-memory for POC)
# =============================================================================

class MetricsCollector:
    """Simple metrics collector for observability."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._metrics = {
                "counters": {},
                "gauges": {},
                "histograms": {},
            }
        return cls._instance
    
    def increment(self, name: str, value: int = 1, tags: dict | None = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self._metrics["counters"][key] = self._metrics["counters"].get(key, 0) + value
    
    def gauge(self, name: str, value: float, tags: dict | None = None):
        """Set a gauge metric."""
        key = self._make_key(name, tags)
        self._metrics["gauges"][key] = value
    
    def histogram(self, name: str, value: float, tags: dict | None = None):
        """Record a histogram value."""
        key = self._make_key(name, tags)
        if key not in self._metrics["histograms"]:
            self._metrics["histograms"][key] = []
        self._metrics["histograms"][key].append(value)
    
    def get_metrics(self) -> dict:
        """Get all collected metrics."""
        return self._metrics.copy()
    
    def reset(self):
        """Reset all metrics."""
        self._metrics = {"counters": {}, "gauges": {}, "histograms": {}}
    
    def _make_key(self, name: str, tags: dict | None) -> str:
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
            return f"{name}[{tag_str}]"
        return name


# Global metrics instance
metrics = MetricsCollector()


# =============================================================================
# INITIALIZATION
# =============================================================================

# Configure logging on module import (can be reconfigured later)
import os

_log_level = os.getenv("LOG_LEVEL", "INFO")
_json_logs = os.getenv("LOG_FORMAT", "json").lower() == "json"
_log_file = os.getenv("LOG_FILE")

configure_logging(level=_log_level, json_format=_json_logs, log_file=_log_file)
