"""
Sync playlist descriptions: simple base line only, no mood or genre.
Uses description_helpers for build_simple_description and sanitization.
Updates incrementally: skip playlists whose snapshot_id has not changed.
"""

import json
from pathlib import Path

import spotipy

from . import settings
from . import logger
from . import api
from . import catalog

_CACHE_FILENAME = ".description_snapshot_cache.json"


def _load_snapshot_cache() -> dict:
    path = settings.get_sync_data_dir() / _CACHE_FILENAME
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_snapshot_cache(cache: dict) -> None:
    path = settings.get_sync_data_dir() / _CACHE_FILENAME
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=0)
    except Exception as e:
        logger.verbose_log(f"  Could not save description cache: {e}")


def _update_playlist_description_with_genres(
    sp: spotipy.Spotify, user_id: str, playlist_id: str, track_uris: list = None
) -> bool:
    """Update playlist description with a single base line. No mood or genre; no parentheses.
    Incremental: skip if playlist snapshot_id unchanged since last run."""
    from src.scripts.automation.description_helpers import (
        build_simple_description,
        get_base_description_line_for_playlist,
        sanitize_description_for_api,
        _strip_parentheses,
    )

    try:
        pl = api.api_call(sp.playlist, playlist_id, fields="description,name,snapshot_id")
        current_description = pl.get("description", "") or ""
        playlist_name = pl.get("name", "Unknown")
        snapshot_id = pl.get("snapshot_id") or ""

        cache = _load_snapshot_cache()
        if snapshot_id and cache.get(playlist_id) == snapshot_id:
            logger.verbose_log(f"  Description '{playlist_name}': unchanged, skipping")
            return False

        if track_uris is None:
            track_uris = list(catalog.get_playlist_tracks(sp, playlist_id, force_refresh=False))
        if not track_uris:
            return False

        logger.verbose_log(
            f"  Description '{playlist_name}': {len(track_uris)} tracks"
        )

        lines = (current_description or "").strip().split("\n")
        base_line = (lines[0].strip() if lines and lines[0].strip() else "") or playlist_name
        if not base_line or base_line.strip() == playlist_name.strip():
            derived = get_base_description_line_for_playlist(playlist_name)
            if derived:
                base_line = derived

        new_description = build_simple_description(
            base_line,
            track_uris,
            max_mood_tags=0,
        )
        new_description = _strip_parentheses(new_description or "")

        new_description = sanitize_description_for_api(
            new_description or "",
            max_length=settings.SPOTIFY_MAX_DESCRIPTION_LENGTH,
        )
        if len(new_description) > settings.SPOTIFY_MAX_DESCRIPTION_LENGTH:
            logger.verbose_log(
                f"  Warning: Description for '{playlist_name}' still {len(new_description)} chars after sanitize, hard truncating"
            )
            new_description = new_description[: settings.SPOTIFY_MAX_DESCRIPTION_LENGTH]

        if not new_description.strip():
            logger.verbose_log(f"  Skipping description update for '{playlist_name}' (description would be empty)")
            return False

        if new_description != current_description:
            try:
                new_description.encode("utf-8")
                api.api_call(
                    sp.user_playlist_change_details,
                    user_id,
                    playlist_id,
                    description=new_description,
                )
                logger.verbose_log(f"  ✅ Updated description for playlist '{playlist_name}' ({len(new_description)} chars)")
                if snapshot_id:
                    cache = _load_snapshot_cache()
                    cache[playlist_id] = snapshot_id
                    _save_snapshot_cache(cache)
                return True
            except UnicodeEncodeError as e:
                logger.verbose_log(f"  ⚠️  Invalid encoding in description for '{playlist_name}': {e}")
                new_description = new_description.encode("utf-8", errors="replace").decode("utf-8")
                try:
                    api.api_call(
                        sp.user_playlist_change_details,
                        user_id,
                        playlist_id,
                        description=new_description[: settings.SPOTIFY_MAX_DESCRIPTION_LENGTH],
                    )
                    logger.verbose_log(f"  ✅ Updated description for playlist '{playlist_name}' after encoding fix")
                    return True
                except Exception as e2:
                    logger.verbose_log(f"  ❌ Failed to update description after encoding fix: {e2}")
                    return False
            except Exception as api_error:
                logger.verbose_log(f"  ❌ Failed to update description via API: {api_error}")
                logger.verbose_log(f"  Description length: {len(new_description)}, preview: {new_description[:100]}...")
                logger.verbose_log(f"  Description repr (first 200): {repr(new_description[:200])}")
                return False
        if snapshot_id:
            cache = _load_snapshot_cache()
            cache[playlist_id] = snapshot_id
            _save_snapshot_cache(cache)
        return False
    except Exception as e:
        logger.verbose_log(f"  Failed to update description: {e}")
        return False
