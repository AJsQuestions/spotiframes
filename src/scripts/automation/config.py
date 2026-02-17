"""
Configuration module for sync automation.

All environment variables and configuration constants are defined here.
"""

import os
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


# Import centralized config helpers
from src.scripts.common.config_helpers import (
    parse_bool_env,
    parse_int_env,
    parse_str_env,
    parse_list_env,
    get_env_or_none,
    require_env
)

# Alias for backward compatibility
_parse_bool_env = parse_bool_env


# Project root and data dir: single source of truth from project_path (SPOTIM8 directory)
from src.scripts.common.project_path import get_project_root, get_data_dir as _get_data_dir

PROJECT_ROOT = get_project_root(__file__)
DATA_DIR = _get_data_dir(__file__)

# Load .env file early so environment variables are available
if DOTENV_AVAILABLE:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

# ============================================================================
# BASIC CONFIGURATION
# ============================================================================
# Most commonly customized settings - users typically only change these
OWNER_NAME = parse_str_env("PLAYLIST_OWNER_NAME", "AJ")
BASE_PREFIX = parse_str_env("PLAYLIST_PREFIX", "Finds")

# Playlist type enable/disable flags
# Set to "false" in .env to disable specific playlist types
ENABLE_MONTHLY = parse_bool_env("PLAYLIST_ENABLE_MONTHLY", True)
ENABLE_MOST_PLAYED = parse_bool_env("PLAYLIST_ENABLE_MOST_PLAYED", True)
ENABLE_DISCOVERY = parse_bool_env("PLAYLIST_ENABLE_DISCOVERY", True)

# Individual prefixes for different playlist types
# Most users don't need to customize these - defaults work well
# Only set if you want different prefixes for different playlist types
PREFIX_MONTHLY = parse_str_env("PLAYLIST_PREFIX_MONTHLY", BASE_PREFIX)
PREFIX_YEARLY = parse_str_env("PLAYLIST_PREFIX_YEARLY", BASE_PREFIX)
PREFIX_MOST_PLAYED = parse_str_env("PLAYLIST_PREFIX_MOST_PLAYED", "Top")
PREFIX_DISCOVERY = parse_str_env("PLAYLIST_PREFIX_DISCOVERY", "Discovery")

# ============================================================================
# PLAYLIST NAME TEMPLATES
# ============================================================================
# Advanced customization - rarely changed, good defaults provided
# Only customize if you need non-standard playlist naming

MONTHLY_NAME_TEMPLATE = parse_str_env(
    "PLAYLIST_TEMPLATE_MONTHLY",
    "{owner}{prefix}{mon}{year}"
)
YEARLY_NAME_TEMPLATE = parse_str_env(
    "PLAYLIST_TEMPLATE_YEARLY",
    "{owner}{prefix}{year}"
)
MOST_PLAYED_TEMPLATE = parse_str_env(
    "PLAYLIST_TEMPLATE_MOST_PLAYED",
    "{owner}{prefix}{mon}{year}"
)
DISCOVERY_TEMPLATE = parse_str_env(
    "PLAYLIST_TEMPLATE_DISCOVERY",
    "{owner}{prefix}{mon}{year}"
)

# ============================================================================
# PLAYLIST LIMITS AND RETENTION
# ============================================================================

KEEP_MONTHLY_MONTHS = parse_int_env("KEEP_MONTHLY_MONTHS", 3)

# ============================================================================
# FORMATTING OPTIONS
# ============================================================================
# Advanced formatting customization - most users don't need to change these
DATE_FORMAT = parse_str_env("PLAYLIST_DATE_FORMAT", "short")  # Options: short, medium, long, numeric
SEPARATOR_MONTH = parse_str_env("PLAYLIST_SEPARATOR_MONTH", "none")  # Options: none, space, dash, underscore
SEPARATOR_PREFIX = parse_str_env("PLAYLIST_SEPARATOR_PREFIX", "none")  # Options: none, space, dash, underscore
CAPITALIZATION = parse_str_env("PLAYLIST_CAPITALIZATION", "preserve")  # Options: title, upper, lower, preserve
DESCRIPTION_TEMPLATE = parse_str_env(
    "PLAYLIST_DESCRIPTION_TEMPLATE",
    "{description} from {period}"
)
# Playlist description: simple log line + optional mood tags (genre support removed)

# ============================================================================
# PATHS AND CONSTANTS
# ============================================================================
# DATA_DIR set above via get_data_dir(__file__) so data lives under SPOTIM8

LIKED_SONGS_PLAYLIST_ID = "__liked_songs__"  # Match spotim8 library constant

# ============================================================================
# API AND RATE LIMITING CONSTANTS
# ============================================================================

# Spotify API limits
SPOTIFY_API_MAX_TRACKS_PER_REQUEST = 100
SPOTIFY_API_MAX_PLAYLIST_ITEMS = 100
SPOTIFY_API_PAGINATION_LIMIT = 50

# Rate limiting
API_RATE_LIMIT_DELAY = 0.1  # Base delay between API calls (seconds)
API_RATE_LIMIT_BACKOFF_MULTIPLIER = 1.5  # Multiplier for backoff on rate errors
API_RATE_LIMIT_MAX_RETRIES = 6  # Maximum retry attempts for rate-limited requests
API_RATE_LIMIT_INITIAL_DELAY = 1.0  # Initial delay on rate limit (seconds)

# ============================================================================
# DESCRIPTION AND FORMATTING CONSTANTS
# ============================================================================

# Spotify limits
SPOTIFY_MAX_DESCRIPTION_LENGTH = 300  # Maximum characters in playlist description

# Description formatting
DESCRIPTION_TRUNCATE_MARGIN = 10  # Characters to leave when truncating
DESCRIPTION_PREVIEW_LENGTH = 100  # Characters to show in preview logs

# Mood tags (Daylist-style): minimal top 5 in playlist descriptions
ENABLE_MOOD_TAGS = parse_bool_env("ENABLE_MOOD_TAGS", False)
MOOD_MAX_TAGS = parse_int_env("MOOD_MAX_TAGS", 5)

# ============================================================================
# TRACK AND PLAYLIST CONSTANTS
# ============================================================================

# Track ID validation
MIN_TRACK_ID_LENGTH = 20  # Minimum length for a valid track ID
TRACK_URI_PREFIX = "spotify:track:"

# Playlist limits
MAX_PLAYLIST_TRACKS = 10000  # Spotify's maximum tracks per playlist
DEFAULT_DISCOVERY_TRACK_LIMIT = 50  # Default limit for discovery tracks

# ============================================================================
# PARALLEL PROCESSING CONSTANTS
# ============================================================================

# Parallel processing
PARALLEL_MIN_TRACKS = 50  # Minimum tracks to enable parallel processing
PARALLEL_DEFAULT_WORKERS = None  # None = auto-detect (CPU count)
PARALLEL_MAX_WORKERS = 8  # Maximum number of parallel workers

# ============================================================================
# MONTH NAME MAPPINGS
# ============================================================================

MONTH_NAMES_SHORT = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"
}
MONTH_NAMES_MEDIUM = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}
MONTH_NAMES = MONTH_NAMES_SHORT  # Default to short for backward compatibility


def reload_from_env() -> None:
    """Re-read all config from environment. Call after setting os.environ (e.g. from CLI or --config file)."""
    global DATA_DIR, OWNER_NAME, BASE_PREFIX, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY
    global PREFIX_MONTHLY, PREFIX_YEARLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY
    global MONTHLY_NAME_TEMPLATE, YEARLY_NAME_TEMPLATE, MOST_PLAYED_TEMPLATE, DISCOVERY_TEMPLATE
    global DATE_FORMAT, SEPARATOR_MONTH, SEPARATOR_PREFIX, CAPITALIZATION
    global KEEP_MONTHLY_MONTHS, DESCRIPTION_TEMPLATE, ENABLE_MOOD_TAGS, MOOD_MAX_TAGS
    DATA_DIR = _get_data_dir(__file__)
    OWNER_NAME = parse_str_env("PLAYLIST_OWNER_NAME", "AJ")
    BASE_PREFIX = parse_str_env("PLAYLIST_PREFIX", "Finds")
    ENABLE_MONTHLY = parse_bool_env("PLAYLIST_ENABLE_MONTHLY", True)
    ENABLE_MOST_PLAYED = parse_bool_env("PLAYLIST_ENABLE_MOST_PLAYED", True)
    ENABLE_DISCOVERY = parse_bool_env("PLAYLIST_ENABLE_DISCOVERY", True)
    PREFIX_MONTHLY = parse_str_env("PLAYLIST_PREFIX_MONTHLY", BASE_PREFIX)
    PREFIX_YEARLY = parse_str_env("PLAYLIST_PREFIX_YEARLY", BASE_PREFIX)
    PREFIX_MOST_PLAYED = parse_str_env("PLAYLIST_PREFIX_MOST_PLAYED", "Top")
    PREFIX_DISCOVERY = parse_str_env("PLAYLIST_PREFIX_DISCOVERY", "Discovery")
    MONTHLY_NAME_TEMPLATE = parse_str_env("PLAYLIST_TEMPLATE_MONTHLY", "{owner}{prefix}{mon}{year}")
    YEARLY_NAME_TEMPLATE = parse_str_env("PLAYLIST_TEMPLATE_YEARLY", "{owner}{prefix}{year}")
    MOST_PLAYED_TEMPLATE = parse_str_env("PLAYLIST_TEMPLATE_MOST_PLAYED", "{owner}{prefix}{mon}{year}")
    DISCOVERY_TEMPLATE = parse_str_env("PLAYLIST_TEMPLATE_DISCOVERY", "{owner}{prefix}{mon}{year}")
    DATE_FORMAT = parse_str_env("PLAYLIST_DATE_FORMAT", "short")
    SEPARATOR_MONTH = parse_str_env("PLAYLIST_SEPARATOR_MONTH", "none")
    SEPARATOR_PREFIX = parse_str_env("PLAYLIST_SEPARATOR_PREFIX", "none")
    CAPITALIZATION = parse_str_env("PLAYLIST_CAPITALIZATION", "preserve")
    KEEP_MONTHLY_MONTHS = parse_int_env("KEEP_MONTHLY_MONTHS", 3)
    DESCRIPTION_TEMPLATE = parse_str_env("PLAYLIST_DESCRIPTION_TEMPLATE", "{description} from {period}")
    ENABLE_MOOD_TAGS = parse_bool_env("ENABLE_MOOD_TAGS", False)
    MOOD_MAX_TAGS = parse_int_env("MOOD_MAX_TAGS", 5)
    # Update _sync_impl.settings so it sees new values
    try:
        from src.scripts.automation import _sync_impl
        s = _sync_impl.settings
        s.DATA_DIR = DATA_DIR
        s.OWNER_NAME = OWNER_NAME
        s.BASE_PREFIX = BASE_PREFIX
        s.KEEP_MONTHLY_MONTHS = KEEP_MONTHLY_MONTHS
        s.ENABLE_MONTHLY = ENABLE_MONTHLY
        s.ENABLE_MOST_PLAYED = ENABLE_MOST_PLAYED
        s.ENABLE_DISCOVERY = ENABLE_DISCOVERY
        s.PREFIX_MONTHLY = PREFIX_MONTHLY
        s.PREFIX_YEARLY = PREFIX_YEARLY
        s.PREFIX_MOST_PLAYED = PREFIX_MOST_PLAYED
        s.PREFIX_DISCOVERY = PREFIX_DISCOVERY
        s.MONTHLY_NAME_TEMPLATE = MONTHLY_NAME_TEMPLATE
        s.DATE_FORMAT = DATE_FORMAT
        s.SEPARATOR_MONTH = SEPARATOR_MONTH
        s.SEPARATOR_PREFIX = SEPARATOR_PREFIX
        s.CAPITALIZATION = CAPITALIZATION
        s.MONTH_NAMES_SHORT = MONTH_NAMES_SHORT
        s.MONTH_NAMES_MEDIUM = MONTH_NAMES_MEDIUM
        s.MONTH_NAMES = MONTH_NAMES
        s.DESCRIPTION_TEMPLATE = DESCRIPTION_TEMPLATE
        s.SPOTIFY_MAX_DESCRIPTION_LENGTH = SPOTIFY_MAX_DESCRIPTION_LENGTH
        s.MOOD_MAX_TAGS = MOOD_MAX_TAGS
        s.DEFAULT_DISCOVERY_TRACK_LIMIT = DEFAULT_DISCOVERY_TRACK_LIMIT
    except Exception:
        pass

