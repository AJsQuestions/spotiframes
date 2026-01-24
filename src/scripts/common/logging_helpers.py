"""
Unified Logging Helpers

Provides consistent logging interface across all modules.
All modules should use these helpers instead of print() or direct logging.
"""

import logging
import sys
from typing import Optional
from datetime import datetime
from pathlib import Path

# Global logger instance
_logger: Optional[logging.Logger] = None
_log_buffer: list[str] = []


def setup_unified_logging(log_dir: Optional[Path] = None, verbose: bool = False) -> logging.Logger:
    """
    Set up unified logging for the application.
    
    Args:
        log_dir: Optional directory for log files. If None, only console logging.
        verbose: If True, enable DEBUG level logging
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    logger = logging.getLogger("spotim8")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        _logger = logger
        return logger
    
    # Console handler with formatted output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Format: [YYYY-MM-DD HH:MM:SS] LEVEL message
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if log_dir provided
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"sync_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance, creating default if needed."""
    global _logger
    if _logger is None:
        setup_unified_logging()
    return _logger


def log(msg: str, level: str = "INFO") -> None:
    """
    Log a message with consistent formatting.
    
    Args:
        msg: Message to log
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = get_logger()
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, msg)
    
    # Also add to buffer for compatibility
    _log_buffer.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {level}: {msg}")


def verbose_log(msg: str) -> None:
    """Log a verbose/debug message."""
    log(msg, level="DEBUG")


def info(msg: str) -> None:
    """Log an info message."""
    log(msg, level="INFO")


def warning(msg: str) -> None:
    """Log a warning message."""
    log(msg, level="WARNING")


def error(msg: str) -> None:
    """Log an error message."""
    log(msg, level="ERROR")


def get_log_buffer() -> list[str]:
    """Get the log buffer (for compatibility with existing code)."""
    return _log_buffer.copy()


def clear_log_buffer() -> None:
    """Clear the log buffer."""
    global _log_buffer
    _log_buffer = []
