"""Structured logging with correlation IDs for request tracking

Created by Sameer
"""
import logging
import json
import uuid
import contextvars
from datetime import datetime
from typing import Any, Dict, Optional

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to log records

    Added by Sameer
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get() or 'no-correlation-id'
        return True


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging

    Added by Sameer
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', 'unknown'),
        }

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'tool_name'):
            log_data['tool_name'] = record.tool_name
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms

        return json.dumps(log_data)


def get_correlation_id() -> str:
    """Get current correlation ID or generate new one

    Added by Sameer
    """
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context

    Added by Sameer
    """
    correlation_id_var.set(correlation_id)


def new_correlation_id() -> str:
    """Generate and set new correlation ID

    Added by Sameer
    """
    cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def setup_structured_logging(
    level: str = "INFO",
    use_json: bool = False,
    add_correlation_id: bool = True
) -> None:
    """
    Setup structured logging for the application.

    Added by Sameer

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: Use JSON formatter for structured logs
        add_correlation_id: Add correlation ID filter
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler()

    if use_json:
        formatter = JSONFormatter()
    else:
        # Human-readable format with correlation ID
        if add_correlation_id:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - [%(correlation_id)s] - %(levelname)s - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

    handler.setFormatter(formatter)

    # Add correlation ID filter
    if add_correlation_id:
        handler.addFilter(CorrelationIDFilter())

    root_logger.addHandler(handler)


def log_tool_execution(
    logger: logging.Logger,
    tool_name: str,
    duration_ms: float,
    success: bool,
    user_id: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """
    Log tool execution with structured data.

    Added by Sameer

    Args:
        logger: Logger instance
        tool_name: Name of the tool
        duration_ms: Execution duration in milliseconds
        success: Whether execution succeeded
        user_id: User ID who triggered the tool
        error: Error message if failed
    """
    extra = {
        'tool_name': tool_name,
        'duration_ms': round(duration_ms, 2),
        'success': success,
    }

    if user_id:
        extra['user_id'] = user_id
    if error:
        extra['error'] = error

    message = f"Tool '{tool_name}' {'succeeded' if success else 'failed'} in {duration_ms:.2f}ms"

    if success:
        logger.info(message, extra=extra)
    else:
        logger.error(message, extra=extra)
