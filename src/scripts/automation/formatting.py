"""
Playlist formatting utilities.

Functions for formatting playlist names and descriptions.

Note: All config values are accessed via the config module at call time (not import time)
so that reload_from_env() is respected.
"""

from . import config as _config


def _get_separator(sep_type: str) -> str:
    """Get separator character based on type."""
    sep_map = {
        "none": "",
        "space": " ",
        "dash": "-",
        "underscore": "_",
    }
    return sep_map.get(sep_type.lower(), "")


def _format_date(month_str: str = None, year: str = None) -> tuple:
    """
    Format date components based on DATE_FORMAT setting.

    Returns:
        (month_str, year_str) tuple with formatted components
    """
    mon = ""
    year_str = ""

    if month_str:
        parts = month_str.split("-")
        full_year = parts[0] if len(parts) >= 1 else ""
        month_num = parts[1] if len(parts) >= 2 else ""

        if _config.DATE_FORMAT == "numeric":
            mon = month_num
            year_str = full_year
        elif _config.DATE_FORMAT == "medium":
            mon = _config.MONTH_NAMES_MEDIUM.get(month_num, month_num)
            year_str = full_year
        elif _config.DATE_FORMAT == "long":
            mon = _config.MONTH_NAMES_MEDIUM.get(month_num, month_num)
            year_str = full_year
        else:  # short (default)
            mon = _config.MONTH_NAMES_SHORT.get(month_num, month_num)
            year_str = full_year[2:] if len(full_year) == 4 else full_year
    elif year:
        # Handle year parameter if provided directly
        if _config.DATE_FORMAT == "numeric":
            year_str = year
        else:
            year_str = year[2:] if len(year) == 4 else year

    # Apply separator between month and year if both present
    if mon and year_str and _config.SEPARATOR_MONTH != "none":
        sep = _get_separator(_config.SEPARATOR_MONTH)
        if _config.DATE_FORMAT == "medium" or _config.DATE_FORMAT == "long":
            # For medium/long, add space before year: "November 2024"
            mon = f"{mon}{sep}{year_str}"
            year_str = ""  # Year is now part of mon
        else:
            # For short/numeric, keep them separate for template
            pass

    return mon, year_str


def _apply_capitalization(text: str) -> str:
    """Apply capitalization style to text."""
    if _config.CAPITALIZATION == "upper":
        return text.upper()
    elif _config.CAPITALIZATION == "lower":
        return text.lower()
    elif _config.CAPITALIZATION == "title":
        return text.title()
    else:  # preserve
        return text


def format_playlist_name(
    template: str,
    month_str: str = None,
    genre: str = None,
    prefix: str = None,
    playlist_type: str = "monthly",
    year: str = None
) -> str:
    """Format playlist name from template.

    Args:
        template: Template string with placeholders
        month_str: Month string like '2025-01' (optional)
        genre: Genre name (optional)
        prefix: Override prefix (optional, uses type-specific prefix if not provided)
        playlist_type: Type of playlist to determine prefix ("monthly", "yearly", "most_played", "discovery")

    Returns:
        Formatted playlist name
    """
    # Determine prefix based on playlist type if not provided (genre support removed)
    if prefix is None:
        prefix_map = {
            "monthly": _config.PREFIX_MONTHLY,
            "yearly": _config.PREFIX_YEARLY,
            "most_played": _config.PREFIX_MOST_PLAYED,
            "discovery": _config.PREFIX_DISCOVERY,
        }
        prefix = prefix_map.get(playlist_type, _config.BASE_PREFIX)

    # Format date components
    mon, year_str = _format_date(month_str, year)

    # Check if month already includes year (for medium/long formats)
    month_includes_year = (_config.DATE_FORMAT == "medium" or _config.DATE_FORMAT == "long") and mon and not year_str

    # Build components (before capitalization)
    owner = _config.OWNER_NAME
    prefix_str = prefix
    genre_str = genre or ""

    # Apply capitalization
    owner = _apply_capitalization(owner)
    prefix_str = _apply_capitalization(prefix_str)
    genre_str = _apply_capitalization(genre_str)
    mon = _apply_capitalization(mon)
    year_str = _apply_capitalization(year_str)

    # Apply separators before formatting
    prefix_sep = _get_separator(_config.SEPARATOR_PREFIX)
    month_sep = _get_separator(_config.SEPARATOR_MONTH) if mon and year_str and not month_includes_year else ""

    # Build formatted components with separators
    if _config.SEPARATOR_PREFIX != "none" and prefix_str:
        # Add separator between owner and prefix if both present
        owner_prefix = f"{owner}{prefix_sep}{prefix_str}" if owner else prefix_str
    else:
        owner_prefix = f"{owner}{prefix_str}" if owner else prefix_str

    # Handle month/year separator
    date_includes_year = False
    if month_includes_year:
        # Month already includes year (e.g., "November 2024")
        date_part = mon
        date_includes_year = True
    elif mon and year_str:
        # Add separator between month and year
        if month_sep:
            date_part = f"{mon}{month_sep}{year_str}"
        else:
            date_part = f"{mon}{year_str}"
        date_includes_year = True
    elif mon:
        date_part = mon
        date_includes_year = False  # No year in date_part
    elif year_str:
        # Only year, no month - keep them separate for template replacement
        date_part = ""
        date_includes_year = False  # Year should be replaced separately in template
    else:
        date_part = ""
        date_includes_year = False

    # Format the name using components
    # Replace template placeholders with formatted components
    formatted = template
    formatted = formatted.replace("{owner}", owner)
    formatted = formatted.replace("{prefix}", prefix_str)
    formatted = formatted.replace("{genre}", genre_str)
    formatted = formatted.replace("{mon}", date_part if (mon or month_includes_year) else "")
    # Only replace {year} if date_part doesn't already include it
    if date_includes_year:
        # Year is already included in date_part, replace {year} with empty string to avoid duplication
        formatted = formatted.replace("{year}", "")
    else:
        # Year should be replaced separately in template (no month, or only year)
        formatted = formatted.replace("{year}", year_str if year_str else "")

    # If template uses {owner}{prefix} pattern, replace with combined version
    if "{owner}{prefix}" in template or (owner and prefix_str and owner_prefix != f"{owner}{prefix_str}"):
        # Try to replace owner+prefix combination
        formatted = formatted.replace(f"{owner}{prefix_str}", owner_prefix)

    return formatted


def format_playlist_description(
    description: str,
    period: str = None,
    date: str = None,
    playlist_type: str = None,
    genre: str = None
) -> str:
    """
    Format playlist description using template.

    Args:
        description: Base description text
        period: Period string (e.g., "Nov 2024", "2024")
        date: Specific date string
        playlist_type: Type of playlist
        genre: Genre name

    Returns:
        Formatted description string
    """
    return _config.DESCRIPTION_TEMPLATE.format(
        description=description or "",
        period=period or "",
        date=date or "",
        type=playlist_type or "",
        genre=genre or ""
    )


def format_yearly_playlist_name(year: str) -> str:
    """Format yearly playlist name like 'AJFinds2025'."""
    # Handle both 4-digit and 2-digit years
    if len(year) == 4:
        year_short = year[2:]
    else:
        year_short = year

    return format_playlist_name(_config.YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="yearly")
