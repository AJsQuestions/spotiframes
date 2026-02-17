"""
Playlist Description Helper Functions

Extracted from sync.py to improve code organization.
Handles description formatting, sanitization, genre tag addition, and mood tags (Daylist-style).
"""

import re
from typing import List, Optional
from collections import Counter

from src.scripts.automation.config import (
    SPOTIFY_MAX_DESCRIPTION_LENGTH,
    DESCRIPTION_TRUNCATE_MARGIN,
    ENABLE_MOOD_TAGS,
    MOOD_MAX_TAGS,
    DESCRIPTION_TEMPLATE,
    OWNER_NAME,
    PREFIX_MONTHLY,
    PREFIX_MOST_PLAYED,
    PREFIX_DISCOVERY,
    PREFIX_YEARLY,
    MONTH_NAMES_SHORT,
)

# Month abbreviations for parsing playlist names (order: try longest first for prefixes)
_MONTH_ABBR = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"


def get_base_description_line_for_playlist(playlist_name: str) -> Optional[str]:
    """
    Derive a human-readable first line for known automated playlist name patterns.

    Used when the current description is empty or exactly the playlist name, so
    automated playlists get a proper first line (e.g. "Liked songs from Jan 26
    (automatically updated)") instead of the raw name.

    Recognized patterns (from config prefixes and templates):
    - Monthly: {owner}{prefix}{mon}{year} -> "Liked songs from Jan 26"
    - Yearly: {owner}{prefix}{year} -> "Liked songs from 2026"
    - Most played: {owner}{prefix}{mon}{year} -> "Most played from Jan 26"
    - Discovery: {owner}{prefix}{mon}{year} -> "Discovery from Jan 26"

    Returns:
        Human-readable base line, or None if the name does not match a known pattern.
    """
    if not playlist_name or not playlist_name.strip():
        return None
    name = playlist_name.strip()
    owner = (OWNER_NAME or "").strip()
    if not owner:
        return None

    # Build regex components; match case-insensitively for owner and prefix
    month_part = rf"({_MONTH_ABBR})(\d{{2}})$"
    year_only_part = r"(\d{2})$"  # 2-digit year at end
    year_4_part = r"(\d{4})$"    # 4-digit year at end

    # Monthly: owner + PREFIX_MONTHLY + Jan + 26
    prefix = (PREFIX_MONTHLY or "").strip()
    if prefix:
        pattern = re.compile(
            r"^" + re.escape(owner) + re.escape(prefix) + month_part,
            re.IGNORECASE
        )
        m = pattern.match(name)
        if m:
            mon, yy = m.group(1), m.group(2)
            return f"Liked songs from {mon} {yy}"

    # Most played: owner + PREFIX_MOST_PLAYED + Jan + 26
    prefix = (PREFIX_MOST_PLAYED or "").strip()
    if prefix:
        pattern = re.compile(
            r"^" + re.escape(owner) + re.escape(prefix) + month_part,
            re.IGNORECASE
        )
        m = pattern.match(name)
        if m:
            mon, yy = m.group(1), m.group(2)
            return f"Most played from {mon} {yy}"

    # Discovery: owner + PREFIX_DISCOVERY + Jan + 26
    prefix = (PREFIX_DISCOVERY or "").strip()
    if prefix:
        pattern = re.compile(
            r"^" + re.escape(owner) + re.escape(prefix) + month_part,
            re.IGNORECASE
        )
        m = pattern.match(name)
        if m:
            mon, yy = m.group(1), m.group(2)
            return f"Discovery from {mon} {yy}"

    # Yearly: owner + PREFIX_YEARLY + 26 or 2026
    prefix = (PREFIX_YEARLY or "").strip()
    if prefix:
        for part, is_4 in [(year_4_part, True), (year_only_part, False)]:
            pattern = re.compile(
                r"^" + re.escape(owner) + re.escape(prefix) + part,
                re.IGNORECASE
            )
            m = pattern.match(name)
            if m:
                y = m.group(1)
                year_full = y if is_4 else ("20" + y if len(y) == 2 else y)
                return f"Liked songs from {year_full}"

    return None


def sanitize_description(description: str, max_length: int = SPOTIFY_MAX_DESCRIPTION_LENGTH) -> str:
    """
    Sanitize and truncate playlist description (generic helper).
    For API submission use sanitize_description_for_api().
    """
    if description is None:
        return ""
    description = str(description)
    description = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', description)
    if len(description) > max_length:
        if "\n" in description:
            lines = description.split("\n")
            if len(lines[0]) <= max_length - DESCRIPTION_TRUNCATE_MARGIN:
                remaining = max_length - len(lines[0]) - 5
                if remaining > 0:
                    truncated_rest = "\n".join(lines[1:])[:remaining]
                    description = f"{lines[0]}\n{truncated_rest}..."
                else:
                    description = lines[0][:max_length - 3] + "..."
            else:
                description = description[:max_length - 3] + "..."
        else:
            description = description[:max_length - 3] + "..."
    return description


def _strip_emoji_and_problematic(s: str) -> str:
    """Remove emoji, zero-width chars, and other symbols that can trigger 400 from Spotify."""
    import unicodedata
    out = []
    for c in s:
        cat = unicodedata.category(c)
        cp = ord(c)
        # Skip control chars (Cc), format chars like zero-width (Cf), surrogates (Cs), private use (Co), unassigned (Cn)
        if cat.startswith("C"):
            continue
        # Skip variation selectors (can break emoji sequences)
        if 0xFE00 <= cp <= 0xFE0F:
            continue
        # Skip symbol/other in emoji/symbol blocks (So with high codepoint = emoji)
        if cat == "So" and cp >= 0x1F300:
            continue
        # Skip modifier symbols in emoji range (e.g. skin tone)
        if cat == "Sk" and 0x1F3FB <= cp <= 0x1F3FF:
            continue
        out.append(c)
    return "".join(out)


def sanitize_description_for_api(description: str, max_length: int = SPOTIFY_MAX_DESCRIPTION_LENGTH) -> str:
    """
    Harden playlist description for Spotify API (avoid 400 Bad Request).

    - Normalizes Unicode to NFC
    - Strips control chars, null bytes, emoji, zero-width chars
    - Truncates to max_length (300) with safe boundary
    - Ensures valid UTF-8 (replaces invalid sequences)

    Args:
        description: Raw description text
        max_length: Spotify limit (300)

    Returns:
        Sanitized string safe for user_playlist_change_details(description=...)
    """
    if description is None:
        return ""
    import unicodedata
    s = str(description)
    # Normalize to NFC (canonical form) so Spotify accepts it
    s = unicodedata.normalize("NFC", s)
    # Remove emoji and other symbols that often cause 400
    s = _strip_emoji_and_problematic(s)
    # Remove control characters and null bytes (keep \\n and \\t)
    s = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", s)
    # Replace \\r so we don't send \\r\\n (some APIs reject \\r)
    s = s.replace("\r", "")
    # Truncate to limit before encoding so we never exceed 300 bytes
    if len(s) > max_length:
        lines = s.split("\n")
        if lines and len(lines[0]) <= max_length - 10:
            rest = "\n".join(lines[1:])
            keep = max_length - len(lines[0]) - 5
            if keep > 0 and len(rest) > keep:
                s = lines[0] + "\n" + rest[:keep] + "..."
            else:
                s = lines[0][: max_length - 3] + "..."
        else:
            s = s[: max_length - 3] + "..."
    if len(s) > max_length:
        s = s[:max_length]
    # Ensure valid UTF-8 (Spotify expects UTF-8)
    s = s.encode("utf-8", errors="replace").decode("utf-8")
    return s


def format_mood_tags(mood_list: List[str], max_tags: int = 5, max_length: int = 120) -> str:
    """
    Format mood labels as a tag string for playlist description (e.g. "Chill • Energetic • Focus").

    Args:
        mood_list: List of mood strings (e.g. from get_mood_tags_for_playlist).
        max_tags: Maximum number of tags to include.
        max_length: Maximum length of tag string.

    Returns:
        Formatted string like "Chill • Energetic • Focus".
    """
    if not mood_list:
        return ""
    tags = mood_list[:max_tags]
    tag_str = " • ".join(tags)
    if len(tag_str) > max_length:
        tag_str = tag_str[:max_length - 10] + "..."
    return tag_str


def add_mood_tags_to_description(
    current_description: str,
    track_uris: List[str],
    max_tags: int = 5,
    preview_urls: Optional[dict] = None,
    mood_cache_dir: Optional[str] = None,
) -> str:
    """
    Add mood tags (Music2Emo song-level only) to playlist description.

    When preview_urls are provided, uses Music2Emo. If not provided, skips mood line.

    Args:
        current_description: Current description text (may already include Genres: ...).
        track_uris: List of track URIs in the playlist.
        max_tags: Maximum number of mood tags to add.
        preview_urls: Dict track_uri -> preview_url (required for mood).
        mood_cache_dir: Optional cache dir for Music2Emo.

    Returns:
        Description with "Moods: ..." added or updated when preview_urls provided.
    """
    if not preview_urls:
        return current_description
    from pathlib import Path
    from src.features.mood_inference import get_mood_tags_for_playlist

    cache_path = Path(mood_cache_dir) if mood_cache_dir else None
    mood_list = get_mood_tags_for_playlist(
        track_uris, preview_urls, max_tags=max_tags, mood_cache_dir=cache_path
    )
    if not mood_list:
        return current_description

    mood_tags = format_mood_tags(mood_list, max_tags=max_tags)
    mood_line = f"Moods: {mood_tags}"

    # Replace or append mood section
    if "Moods:" in current_description:
        lines = current_description.split("\n")
        new_lines = []
        skip_until_newline = False
        for line in lines:
            if "Moods:" in line:
                skip_until_newline = True
                new_lines.append(mood_line)
            elif skip_until_newline and line.strip() == "":
                skip_until_newline = False
                new_lines.append(line)
            elif not skip_until_newline:
                new_lines.append(line)
        return "\n".join(new_lines)
    if current_description:
        return f"{current_description}\n{mood_line}"
    return mood_line


def _strip_parentheses(text: str) -> str:
    """Remove parenthetical segments and trim. No mood or genre; no parentheses in descriptions."""
    if not text:
        return text
    # Remove (...) and [...] and any content inside
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text)
    text = re.sub(r"\s*\[[^\]]*\]\s*", " ", text)
    return " ".join(text.split()).strip()


def build_simple_description(
    base_line: str,
    track_uris: List[str],
    max_mood_tags: int = None,
    preview_urls: Optional[dict] = None,
    mood_cache_dir: Optional[str] = None,
    audio_features_fallback: Optional[list] = None,
) -> str:
    """
    Build playlist description: single base line, no mood or genre.
    Parentheses are stripped from the result.
    """
    line = _strip_parentheses(base_line.strip()) if base_line else ""
    return line
