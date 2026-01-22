"""
Centralized configuration helpers.

Provides consistent utilities for:
- Environment variable parsing
- Boolean parsing
- Configuration validation
- Type-safe configuration access
"""

import os
from typing import Optional, Any, Union
from pathlib import Path


def parse_bool_env(key: str, default: bool = False) -> bool:
    """
    Parse boolean environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
    
    Returns:
        Boolean value parsed from environment
    """
    value = os.environ.get(key, str(default)).lower().strip()
    return value in ("true", "1", "yes", "on")


def parse_int_env(key: str, default: int = 0) -> int:
    """
    Parse integer environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
    
    Returns:
        Integer value parsed from environment
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_float_env(key: str, default: float = 0.0) -> float:
    """
    Parse float environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
    
    Returns:
        Float value parsed from environment
    """
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_str_env(key: str, default: str = "") -> str:
    """
    Parse string environment variable.
    
    Args:
        key: Environment variable name
        default: Default value if not set
    
    Returns:
        String value from environment, or default
    """
    return os.environ.get(key, default).strip()


def parse_list_env(key: str, default: Optional[list] = None, separator: str = ",") -> list:
    """
    Parse list from environment variable (comma-separated).
    
    Args:
        key: Environment variable name
        default: Default value if not set
        separator: Separator character (default: comma)
    
    Returns:
        List of strings parsed from environment
    """
    if default is None:
        default = []
    value = os.environ.get(key)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(separator) if item.strip()]


def get_env_or_none(key: str) -> Optional[str]:
    """
    Get environment variable or None if not set.
    
    Args:
        key: Environment variable name
    
    Returns:
        Value or None if not set
    """
    value = os.environ.get(key)
    return value.strip() if value else None


def require_env(key: str, error_message: Optional[str] = None) -> str:
    """
    Require environment variable to be set.
    
    Args:
        key: Environment variable name
        error_message: Custom error message (default: includes key name)
    
    Returns:
        Value of environment variable
    
    Raises:
        ValueError: If environment variable is not set
    """
    value = os.environ.get(key)
    if not value or not value.strip():
        if error_message:
            raise ValueError(error_message)
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value.strip()


def validate_path_env(key: str, must_exist: bool = False, must_be_dir: bool = False) -> Optional[Path]:
    """
    Validate path from environment variable.
    
    Args:
        key: Environment variable name
        must_exist: Whether path must exist
        must_be_dir: Whether path must be a directory
    
    Returns:
        Path object or None if not set
    
    Raises:
        ValueError: If validation fails
    """
    value = os.environ.get(key)
    if not value:
        return None
    
    path = Path(value).expanduser().resolve()
    
    if must_exist and not path.exists():
        raise ValueError(f"Path from {key} does not exist: {path}")
    
    if must_be_dir and not path.is_dir():
        raise ValueError(f"Path from {key} is not a directory: {path}")
    
    return path
