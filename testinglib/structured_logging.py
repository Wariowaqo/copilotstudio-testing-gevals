"""
=============================================================================
Structured Logging Module for Copilot Studio Testing
=============================================================================

PHASE 3: Observability - Structured Logging

PURPOSE:
    Provides JSON-structured logging for enterprise observability:
    - SIEM integration (Splunk, Azure Sentinel, etc.)
    - Log aggregation (ELK Stack, Azure Log Analytics)
    - Correlation across distributed systems
    - Performance monitoring and alerting

WHY THIS MATTERS:
    - Plain text logs are hard to parse and analyze at scale
    - Structured logs enable:
      * Automated alerting on specific conditions
      * Dashboards and visualizations
      * Correlation of events across services
      * Compliance and audit requirements
    - Correlation IDs allow tracing requests across services

USAGE:
    # Basic setup (call once at application startup)
    from testinglib.structured_logging import setup_logging, get_logger
    
    setup_logging(level="INFO", json_format=True)
    
    # Get a logger for your module
    logger = get_logger(__name__)
    
    # Log with context
    logger.info("Test started", test_name="my_test", agent="copilot-1")
    
    # Log with operation tracking
    with logger.operation("evaluate_response") as op:
        op.set_context(test_case="TC001", agent="copilot-1")
        result = evaluate(response)
        op.set_result(score=result.score)
    
    # Structured exception logging
    try:
        risky_operation()
    except Exception as e:
        logger.exception("Operation failed", operation="risky", error_code="E001")

OUTPUT FORMAT (JSON):
    {
        "timestamp": "2026-01-25T10:30:00.000Z",
        "level": "INFO",
        "logger": "tests.multi_turn_eval",
        "message": "Test started",
        "correlation_id": "abc-123-def",
        "service": "copilot-studio-testing",
        "environment": "dev",
        "test_name": "my_test",
        "agent": "copilot-1"
    }

CONFIGURATION:
    Environment variables:
    - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
    - LOG_FORMAT: "json" or "text"
    - LOG_FILE: Path to log file (optional)
    - SERVICE_NAME: Name of this service in logs
    - ENVIRONMENT: Environment name (dev, staging, prod)

=============================================================================
"""

import json
import logging
import os
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar
from contextlib import contextmanager

# =============================================================================
# CONTEXT VARIABLES (for correlation across async operations)
# =============================================================================

# Correlation ID for tracing requests
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

# Additional context that should be included in all logs
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set the correlation ID for the current context.
    
    Args:
        correlation_id: ID to set, or None to generate new UUID
        
    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    _correlation_id.set(correlation_id)
    return correlation_id


def get_log_context() -> Dict[str, Any]:
    """Get additional context to include in logs."""
    return _log_context.get().copy()


def set_log_context(**kwargs):
    """
    Set additional context for all logs in this context.
    
    Example:
        set_log_context(user_id="123", tenant="abc")
    """
    ctx = _log_context.get().copy()
    ctx.update(kwargs)
    _log_context.set(ctx)


def clear_log_context():
    """Clear all additional log context."""
    _log_context.set({})


# =============================================================================
# LOG RECORD STRUCTURE
# =============================================================================

@dataclass
class StructuredLogRecord:
    """
    Structured log record for JSON output.
    
    This defines the schema of log entries.
    """
    timestamp: str
    level: str
    logger: str
    message: str
    correlation_id: Optional[str] = None
    service: str = "copilot-studio-testing"
    environment: str = "unknown"
    
    # Optional fields
    duration_ms: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Additional context (arbitrary key-value pairs)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "service": self.service,
            "environment": self.environment,
        }
        
        # Add optional fields if present
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.error_type:
            result["error_type"] = self.error_type
        if self.error_message:
            result["error_message"] = self.error_message
        if self.stack_trace:
            result["stack_trace"] = self.stack_trace
        
        # Merge context directly into result
        result.update(self.context)
        
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


# =============================================================================
# JSON FORMATTER
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.
    
    Output is a single JSON object per line, suitable for:
    - Log aggregation systems
    - SIEM tools
    - Streaming to cloud logging services
    """
    
    def __init__(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        include_stack_trace: bool = True,
    ):
        """
        Initialize JSON formatter.
        
        Args:
            service_name: Name of this service (from env or default)
            environment: Environment name (from env or default)
            include_stack_trace: Whether to include stack traces for errors
        """
        super().__init__()
        self.service_name = service_name or os.environ.get("SERVICE_NAME", "copilot-studio-testing")
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.include_stack_trace = include_stack_trace
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # Build the structured record
        structured = StructuredLogRecord(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            correlation_id=get_correlation_id(),
            service=self.service_name,
            environment=self.environment,
        )
        
        # Add extra context from the log call
        if hasattr(record, '__dict__'):
            # Standard fields to exclude
            standard_fields = {
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'taskName'
            }
            
            for key, value in record.__dict__.items():
                if key not in standard_fields and not key.startswith('_'):
                    structured.context[key] = value
        
        # Add global log context
        structured.context.update(get_log_context())
        
        # Handle exceptions
        if record.exc_info:
            structured.error_type = record.exc_info[0].__name__ if record.exc_info[0] else None
            structured.error_message = str(record.exc_info[1]) if record.exc_info[1] else None
            if self.include_stack_trace and record.exc_info[2]:
                structured.stack_trace = ''.join(traceback.format_exception(*record.exc_info))
        
        return structured.to_json()


class PrettyFormatter(logging.Formatter):
    """
    Human-readable formatter for local development.
    
    Output example:
        2026-01-25 10:30:00 [INFO] tests.eval - Test started (correlation_id=abc-123)
    """
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',      # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        """Initialize with optional color support."""
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for human readability."""
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Level with optional color
        level = record.levelname
        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.COLORS['RESET']
            level = f"{color}{level:8}{reset}"
        else:
            level = f"{level:8}"
        
        # Correlation ID
        corr_id = get_correlation_id()
        corr_str = f" (corr={corr_id[:8]})" if corr_id else ""
        
        # Extra context
        extras = []
        standard_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'message', 'taskName'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_fields and not key.startswith('_'):
                extras.append(f"{key}={value}")
        
        extra_str = f" | {', '.join(extras)}" if extras else ""
        
        # Build message
        msg = f"{timestamp} [{level}] {record.name} - {record.getMessage()}{corr_str}{extra_str}"
        
        # Add exception info
        if record.exc_info:
            msg += "\n" + ''.join(traceback.format_exception(*record.exc_info))
        
        return msg


# =============================================================================
# LOGGER WRAPPER
# =============================================================================

class StructuredLogger:
    """
    Wrapper around standard logger with structured logging support.
    
    Provides:
    - Context-aware logging with correlation IDs
    - Operation tracking with timing
    - Extra fields in log calls
    
    Usage:
        logger = StructuredLogger(__name__)
        logger.info("Message", key="value", another_key=123)
    """
    
    def __init__(self, name: str):
        """Initialize with logger name (usually __name__)."""
        self._logger = logging.getLogger(name)
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method that adds kwargs as extras."""
        self._logger.log(level, message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional context."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with optional context."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with optional context."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with optional context."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with optional context."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with stack trace."""
        self._logger.exception(message, extra=kwargs)
    
    @contextmanager
    def operation(self, name: str, **initial_context):
        """
        Context manager for tracking an operation.
        
        Automatically logs start/end and measures duration.
        
        Usage:
            with logger.operation("evaluate_test", test_id="TC001") as op:
                result = do_something()
                op.set_result(score=result.score)
        
        Yields:
            OperationContext for adding context during operation
        """
        op = OperationContext(self, name)
        op.set_context(**initial_context)
        
        try:
            op.start()
            yield op
            op.success()
        except Exception as e:
            op.failure(e)
            raise


class OperationContext:
    """
    Context for tracking an operation's lifecycle.
    
    Created by StructuredLogger.operation().
    """
    
    def __init__(self, logger: StructuredLogger, operation_name: str):
        self.logger = logger
        self.operation_name = operation_name
        self.context: Dict[str, Any] = {}
        self.start_time: Optional[float] = None
        self._result: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Add context that will be included in logs."""
        self.context.update(kwargs)
    
    def set_result(self, **kwargs):
        """Set result values to include in completion log."""
        self._result.update(kwargs)
    
    def start(self):
        """Called when operation starts."""
        self.start_time = time.time()
        self.logger.info(
            f"Operation started: {self.operation_name}",
            operation=self.operation_name,
            phase="start",
            **self.context
        )
    
    def success(self):
        """Called when operation completes successfully."""
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        self.logger.info(
            f"Operation completed: {self.operation_name}",
            operation=self.operation_name,
            phase="complete",
            status="success",
            duration_ms=duration_ms,
            **self.context,
            **self._result
        )
    
    def failure(self, exception: Exception):
        """Called when operation fails."""
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        self.logger.error(
            f"Operation failed: {self.operation_name}",
            operation=self.operation_name,
            phase="complete",
            status="error",
            duration_ms=duration_ms,
            error_type=type(exception).__name__,
            error_message=str(exception),
            **self.context
        )


# =============================================================================
# SETUP FUNCTIONS
# =============================================================================

def setup_logging(
    level: str = "INFO",
    json_format: Optional[bool] = None,
    log_file: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
):
    """
    Set up structured logging for the application.
    
    Call this once at application startup:
        from testinglib.structured_logging import setup_logging
        setup_logging(level="DEBUG", json_format=True)
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: True for JSON, False for pretty text, None for auto-detect
        log_file: Optional path to write logs to file
        service_name: Service name for structured logs
        environment: Environment name (dev, staging, prod)
    """
    # Determine format (auto-detect: JSON in CI/production, pretty for local)
    if json_format is None:
        ci_env = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
        env = os.environ.get("ENVIRONMENT", "dev")
        json_format = bool(ci_env) or env in ("staging", "prod", "production")
    
    # Get settings from environment
    level = os.environ.get("LOG_LEVEL", level).upper()
    log_file = log_file or os.environ.get("LOG_FILE")
    service_name = service_name or os.environ.get("SERVICE_NAME", "copilot-studio-testing")
    environment = environment or os.environ.get("ENVIRONMENT", "dev")
    
    # Create formatter
    if json_format:
        formatter = JSONFormatter(service_name=service_name, environment=environment)
    else:
        formatter = PrettyFormatter(use_colors=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter(service_name=service_name, environment=environment))
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)
    
    # Log setup completion
    logger = get_logger(__name__)
    logger.info(
        "Logging configured",
        log_level=level,
        format="json" if json_format else "pretty",
        log_file=log_file,
        service=service_name,
        environment=environment
    )


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for the given name.
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Hello", key="value")
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


# =============================================================================
# DECORATORS
# =============================================================================

T = TypeVar('T')


def log_operation(
    operation_name: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False,
) -> Callable:
    """
    Decorator to automatically log function calls.
    
    Usage:
        @log_operation()
        async def my_function(arg1, arg2):
            ...
        
        @log_operation(operation_name="custom-name", log_result=True)
        def another_function():
            ...
    
    Args:
        operation_name: Custom operation name (default: function name)
        log_args: If True, log function arguments
        log_result: If True, log function return value
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        name = operation_name or f"{func.__module__}.{func.__name__}"
        logger = get_logger(func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with logger.operation(name) as op:
                if log_args:
                    op.set_context(args=str(args), kwargs=str(kwargs))
                
                result = await func(*args, **kwargs)
                
                if log_result:
                    op.set_result(result=str(result)[:200])
                
                return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with logger.operation(name) as op:
                if log_args:
                    op.set_context(args=str(args), kwargs=str(kwargs))
                
                result = func(*args, **kwargs)
                
                if log_result:
                    op.set_result(result=str(result)[:200])
                
                return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    """
    Demonstrate structured logging.
    
    Usage:
        python -m testinglib.structured_logging
        LOG_FORMAT=json python -m testinglib.structured_logging
    """
    print("=" * 60)
    print("STRUCTURED LOGGING DEMO")
    print("=" * 60)
    
    # Setup logging (pretty format for demo)
    json_mode = os.environ.get("LOG_FORMAT") == "json"
    setup_logging(level="DEBUG", json_format=json_mode)
    
    # Get logger
    logger = get_logger("demo")
    
    # Set correlation ID for this "request"
    set_correlation_id("demo-123-abc")
    
    # Basic logging with context
    print("\n1. Basic logging with context:")
    logger.info("User started test", user_id="user-123", test_suite="smoke")
    logger.debug("Loading configuration", config_file="test.yaml")
    logger.warning("Deprecated API used", api_version="v1", replacement="v2")
    
    # Operation tracking
    print("\n2. Operation tracking:")
    with logger.operation("evaluate_agent", agent_name="copilot-1") as op:
        time.sleep(0.1)  # Simulate work
        op.set_result(score=0.85, passed=True)
    
    # Error logging
    print("\n3. Error logging:")
    try:
        raise ValueError("Something went wrong")
    except Exception as e:
        logger.exception("Operation failed", operation="demo")
    
    print("\n" + "=" * 60)
    print("Try with JSON format: LOG_FORMAT=json python -m testinglib.structured_logging")
    print("=" * 60)
