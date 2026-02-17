"""
Playlist update utilities.

Functions for updating monthly playlists (Finds, Top, Discovery).

This module is extracted from sync.py and uses late imports to access
utilities from sync.py to avoid circular dependencies.
"""

import spotipy
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

from .formatting import format_playlist_name, format_playlist_description
from .error_handling import handle_errors

@handle_errors(reraise=False, default_return={}, log_error=True)
def update_monthly_playlists(sp: spotipy.Spotify, keep_last_n_months: int = 3) -> dict:
    """Update monthly playlists for the last N months by calendar (including current month).
    
    Uses calendar-based "last N months" so when a new month starts (e.g. 1 Feb), the new
    month's playlist (e.g. AJFndsFeb26) is created immediately, even if empty. Older
    months are merged into yearly playlists by consolidate_old_monthly_playlists().
    Only creates/updates monthly playlists for the last N months (default: 3).
    
    Data Sources:
    - "Finds" playlists: Use API data (liked songs) - always up-to-date
    - Top and Discovery playlists: Use streaming history from exports (Vibes/OnRepeat removed)
      - Streaming history is updated periodically and may lag behind API data
      - Recent months may be incomplete if export is outdated
      - Missing history results in empty playlists for those types
    
    Args:
        keep_last_n_months: Number of recent months to keep as monthly playlists (default: 3)
    
    Note: This function only ADDS tracks to playlists. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    # Late imports from sync.py
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, MONTHLY_NAME_TEMPLATE, get_existing_playlists, get_user_info, get_playlist_tracks, api_call,
        _chunked, _update_playlist_description_with_genres, _playlist_tracks_cache, _invalidate_playlist_cache
    )
    log(f"\n--- Monthly Playlists (Last {keep_last_n_months} Months Only) ---")
    
    # Log enabled playlist types
    # NOTE: Only "Finds" playlists are created monthly. Top/Dscvr are yearly only.
    enabled_types = []
    if ENABLE_MONTHLY:
        enabled_types.append("Finds (monthly)")
    if ENABLE_MOST_PLAYED:
        enabled_types.append("Top (yearly only)")
    # Vbz/Rpt removed - only Top and Discovery kept for yearly
    # if ENABLE_TIME_BASED:
    #     enabled_types.append("Vbz (yearly only)")
    # if ENABLE_REPEAT:
    #     enabled_types.append("Rpt (yearly only)")
    if ENABLE_DISCOVERY:
        enabled_types.append("Dscvr (yearly only)")
    
    if enabled_types:
        log(f"  Enabled playlist types: {', '.join(enabled_types)}")
        log(f"  📌 Note: Top/Dscvr are created as yearly playlists only (no monthly). Vbz/Rpt removed.")
    else:
        log("  ⚠️  No playlist types enabled - check .env file")
        return {}
    
    # Load streaming history for Top/Vibes/OnRepeat/Discover playlists
    # NOTE: Streaming history comes from periodic Spotify exports and may lag behind API data.
    # API data (liked songs) is always more up-to-date than streaming history exports.
    # If streaming history is missing or incomplete, these playlist types will be empty or incomplete.
    from src.analysis.streaming_history import load_streaming_history
    history_df = load_streaming_history(DATA_DIR)
    if history_df is not None and not history_df.empty:
        # Ensure timestamp is datetime
        if 'timestamp' in history_df.columns:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce', utc=True)
        
        # Check data freshness - warn if streaming history is significantly behind
        # Streaming history comes from periodic exports, so it may lag behind API data
        if 'timestamp' in history_df.columns:
            try:
                latest_history = history_df['timestamp'].max()
                if pd.notna(latest_history):
                    # Convert to naive datetime for comparison if needed
                    if latest_history.tzinfo:
                        latest_naive = latest_history.replace(tzinfo=None)
                        now = datetime.now()
                    else:
                        latest_naive = latest_history
                        now = datetime.now()
                    
                    days_behind = (now - latest_naive).days
                    if days_behind > 30:
                        latest_str = latest_history.strftime('%Y-%m-%d') if hasattr(latest_history, 'strftime') else str(latest_history)
                        log(f"  ⚠️  Streaming history is {days_behind} days old (latest: {latest_str})")
                        log(f"      Recent months may be incomplete. Export new data for up-to-date playlists.")
            except Exception:
                pass  # Skip freshness check if there's an error
        
        log(f"  Loaded streaming history: {len(history_df):,} records")
    else:
        log("  ⚠️  No streaming history found - Discovery playlists will be empty")
        log("      Export streaming history data to enable these playlist types")
    
    # Load liked songs data for "Finds" playlists (API data only - never uses streaming history)
    playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
    all_month_to_tracks = {}
    
    if playlist_tracks_path.exists():
        library = pd.read_parquet(playlist_tracks_path)
        liked = library[library["playlist_id"].astype(str) == LIKED_SONGS_PLAYLIST_ID].copy()
        
        if not liked.empty:
            # Parse timestamps
            added_col = None
            for col in ["added_at", "playlist_added_at", "track_added_at"]:
                if col in liked.columns:
                    added_col = col
                    break
            
            if added_col:
                liked[added_col] = pd.to_datetime(liked[added_col], errors="coerce", utc=True)
                liked["month"] = liked[added_col].dt.to_period("M").astype(str)
                
                # Handle both track_uri and track_id columns
                if "track_uri" in liked.columns:
                    liked["_uri"] = liked["track_uri"]
                else:
                    liked["_uri"] = liked["track_id"].map(_to_uri)
                
                # Build month -> tracks mapping for "Finds" playlists (API data only)
                for month, group in liked.groupby("month"):
                    uris = group["_uri"].dropna().tolist()
                    seen = set()
                    unique = [u for u in uris if not (u in seen or seen.add(u))]
                    all_month_to_tracks[month] = {"monthly": unique}
                
                log(f"  Loaded liked songs (API data) for 'Finds' playlists: {len(all_month_to_tracks)} month(s)")
        else:
            log("  ⚠️  No liked songs found in library data - 'Finds' playlists will be empty")
    else:
        log("  ⚠️  Library data not found - 'Finds' playlists will be empty (run full sync first)")
    
    # Get months for "Finds" playlists (API data only - liked songs)
    finds_months = set(all_month_to_tracks.keys())
    
    # Get months for other playlist types (streaming history)
    history_months = set()
    if history_df is not None and not history_df.empty:
        history_df['month'] = history_df['timestamp'].dt.to_period('M').astype(str)
        history_months = set(history_df['month'].unique())
    
    # Last N months by calendar (always include current month so new month gets a playlist on rollover)
    # Example: on 1 Feb 2026 with N=3 -> [2025-12, 2026-01, 2026-02]; create AJFndsFeb26, AJFndsJan26, AJFndsDec25
    now = datetime.now()
    calendar_last_n = [(now - relativedelta(months=i)).strftime("%Y-%m") for i in range(keep_last_n_months)]
    recent_months = sorted(set(calendar_last_n))
    all_months = finds_months | history_months
    older_months = [m for m in sorted(all_months) if m not in recent_months] if all_months else []
    if older_months:
        log(f"📅 Keeping last {keep_last_n_months} months (by calendar) as monthly: {', '.join(recent_months)}")
        log(f"📦 Older months will be merged into yearly playlists then removed: {', '.join(older_months[:10])}{'…' if len(older_months) > 10 else ''}")
    if finds_months:
        finds_in_scope = [m for m in recent_months if m in finds_months]
        log(f"   📌 'Finds' will use API data (liked songs) for {len(finds_in_scope)} of {len(recent_months)} month(s)")

    if not recent_months:
        log("No months to process")
        return {}
    
    log(f"Processing {len(recent_months)} month(s) for all playlist types...")
    
    # Get existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Define playlist types and their configurations
    # "Finds" playlists use API data (liked songs) only - never streaming history
    # Other playlists use streaming history data
    # Only include playlist types that are enabled in .env
    # NOTE: Dscvr is created as yearly playlists only (no monthly). Top/Vbz/Rpt removed.
    # Only "Finds" playlists are created monthly
    playlist_configs = []
    
    if ENABLE_MONTHLY:
        playlist_configs.append((
            "monthly", MONTHLY_NAME_TEMPLATE, "Liked songs", 
            lambda m: all_month_to_tracks.get(m, {}).get("monthly", [])  # API data only
        ))
    
    # Top/Vbz/Rpt/Dscvr are NOT created as monthly playlists - only yearly
    # They are created in consolidate_old_monthly_playlists() for all years with streaming history
    
    if not playlist_configs:
        log("⚠️  All playlist types are disabled in .env file. No playlists will be created.")
        return {}
    
    month_to_tracks = {}
    
    for month in sorted(recent_months):
        month_to_tracks[month] = {}
        
        for playlist_type, template, description, get_tracks_fn in playlist_configs:
            # Get tracks for this playlist type and month (may be empty for new month)
            track_uris = get_tracks_fn(month) or []
            month_to_tracks[month][playlist_type] = track_uris
            
            # Format playlist name (all types use monthly format for monthly playlists)
            name = format_playlist_name(template, month, playlist_type=playlist_type)
            
            # Create or update even when empty so new month gets a playlist on rollover (e.g. AJFndsFeb26 on 1 Feb)
            if name in existing:
                pid = existing[name]
                already = get_playlist_tracks(sp, pid)
                to_add = [u for u in track_uris if u not in already]
                
                if to_add:
                    for chunk in _chunked(to_add, 50):
                        api_call(sp.playlist_add_items, pid, chunk)
                    if pid in _playlist_tracks_cache:
                        del _playlist_tracks_cache[pid]
                    log(f"  {name}: +{len(to_add)} tracks ({len(track_uris)} total)")
                else:
                    log(f"  {name}: up to date ({len(track_uris)} tracks)")
                # Update description with genre tags (even if 0 tracks)
                _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
            else:
                # Create playlist (may be empty for first day of new month)
                from calendar import monthrange
                year, month_num = map(int, month.split("-"))
                last_day = monthrange(year, month_num)[1]
                created_at = datetime(year, month_num, last_day, 23, 59, 59)
                
                verbose_log(f"Creating new playlist '{name}' for {month} (type={playlist_type})...")
                pl = api_call(
                    sp.user_playlist_create,
                    user_id,
                    name,
                    public=False,
                    description=format_playlist_description(description, period=month, playlist_type=playlist_type),
                )
                pid = pl["id"]
                verbose_log(f"  Created playlist '{name}' with id {pid}")
                
                # Add tracks
                verbose_log(f"  Adding {len(track_uris)} tracks in chunks...")
                chunk_count = 0
                for chunk in _chunked(track_uris, 50):
                    chunk_count += 1
                    verbose_log(f"    Adding chunk {chunk_count} ({len(chunk)} tracks)...")
                    api_call(sp.playlist_add_items, pid, chunk)
                
                # Update description with genre tags
                _update_playlist_description_with_genres(sp, user_id, pid, track_uris)
                
                _invalidate_playlist_cache()
                verbose_log(f"  Invalidated playlist cache after creating new playlist")
                log(f"  {name}: created with {len(track_uris)} tracks")
    
    return month_to_tracks


@handle_errors(reraise=False, default_return=None, log_error=True)
def update_current_year_playlists(sp: spotipy.Spotify) -> None:
    """Update the current year's yearly playlists (Finds, Top, Discovery) with new liked songs / most-played / discovery.
    Only adds tracks; never removes. Run after sync so library and history are up to date.
    """
    from .sync import (
        log, verbose_log, DATA_DIR, ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        get_existing_playlists, get_user_info, get_playlist_tracks, get_liked_song_uris, api_call,
        _chunked, _update_playlist_description_with_genres, _invalidate_playlist_cache, _to_uri,
    )
    from .formatting import format_yearly_playlist_name, format_playlist_name, format_playlist_description
    from .config import YEARLY_NAME_TEMPLATE

    log("\n--- Update Current Year Playlists (Finds, Top, Discovery) ---")
    current_year = datetime.now().year
    year_short = str(current_year)[2:]
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]

    # Finds: add current liked songs to current year's yearly playlist
    if ENABLE_MONTHLY:
        finds_name = format_yearly_playlist_name(str(current_year))
        if finds_name in existing:
            pid = existing[finds_name]
            liked_uris = get_liked_song_uris(sp)
            already = get_playlist_tracks(sp, pid)
            to_add = [u for u in liked_uris if u and isinstance(u, str) and u not in already]
            if to_add:
                for chunk in _chunked(to_add, 50):
                    valid = [u for u in chunk if u and isinstance(u, str)]
                    if valid:
                        api_call(sp.playlist_add_items, pid, valid)
                _invalidate_playlist_cache()
                log(f"  {finds_name}: +{len(to_add)} tracks (total liked: {len(liked_uris)})")
            else:
                log(f"  {finds_name}: up to date")
        else:
            # Create current year Finds playlist with all liked songs
            liked_uris = get_liked_song_uris(sp)
            pl = api_call(
                sp.user_playlist_create,
                user_id,
                finds_name,
                public=False,
                description=format_playlist_description("Liked songs", period=str(current_year), playlist_type="monthly"),
            )
            pid = pl["id"]
            valid_uris = [u for u in liked_uris if u and isinstance(u, str)]
            for chunk in _chunked(valid_uris, 50):
                if chunk:
                    api_call(sp.playlist_add_items, pid, chunk)
            _update_playlist_description_with_genres(sp, user_id, pid, liked_uris)
            _invalidate_playlist_cache()
            log(f"  {finds_name}: created with {len(liked_uris)} tracks")

    # Top & Discovery: use streaming history for current year
    from src.analysis.streaming_history import load_streaming_history
    from src.scripts.automation._sync_impl.history import get_most_played_tracks, get_discovery_tracks
    history_df = load_streaming_history(DATA_DIR)
    time_col = None
    if history_df is not None and not history_df.empty:
        if "timestamp" in history_df.columns:
            time_col = "timestamp"
        elif "endTime" in history_df.columns:
            time_col = "endTime"
    if history_df is not None and not history_df.empty and time_col:
        history_df = history_df.copy()
        history_df["timestamp"] = pd.to_datetime(history_df[time_col], errors="coerce", utc=True)
        history_df["year"] = history_df["timestamp"].dt.year
        year_df = history_df[history_df["year"] == current_year]
        if not year_df.empty:
            if ENABLE_MOST_PLAYED:
                top_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="most_played")
                top_uris = get_most_played_tracks(year_df, month_str=None, limit=100)
                if top_name in existing and top_uris:
                    pid = existing[top_name]
                    already = get_playlist_tracks(sp, pid)
                    to_add = [u for u in top_uris if u and isinstance(u, str) and u not in already]
                    if to_add:
                        for chunk in _chunked(to_add, 50):
                            valid = [u for u in chunk if u and isinstance(u, str)]
                            if valid:
                                api_call(sp.playlist_add_items, pid, valid)
                        _invalidate_playlist_cache()
                        log(f"  {top_name}: +{len(to_add)} tracks")
                    else:
                        log(f"  {top_name}: up to date")
                elif top_uris and top_name not in existing:
                    pl = api_call(sp.user_playlist_create, user_id, top_name, public=False,
                        description=format_playlist_description("Most played", period=str(current_year), playlist_type="most_played"))
                    valid_top = [u for u in top_uris if u and isinstance(u, str)]
                    for chunk in _chunked(valid_top, 50):
                        if chunk:
                            api_call(sp.playlist_add_items, pl["id"], chunk)
                    _update_playlist_description_with_genres(sp, user_id, pl["id"], top_uris)
                    _invalidate_playlist_cache()
                    log(f"  {top_name}: created with {len(top_uris)} tracks")
            if ENABLE_DISCOVERY:
                disc_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="discovery")
                disc_uris = get_discovery_tracks(year_df, month_str=None, limit=100)
                if disc_name in existing and disc_uris:
                    pid = existing[disc_name]
                    already = get_playlist_tracks(sp, pid)
                    to_add = [u for u in disc_uris if u and isinstance(u, str) and u not in already]
                    if to_add:
                        for chunk in _chunked(to_add, 50):
                            valid = [u for u in chunk if u and isinstance(u, str)]
                            if valid:
                                api_call(sp.playlist_add_items, pid, valid)
                        _invalidate_playlist_cache()
                        log(f"  {disc_name}: +{len(to_add)} tracks")
                    else:
                        log(f"  {disc_name}: up to date")
                elif disc_uris and disc_name not in existing:
                    pl = api_call(sp.user_playlist_create, user_id, disc_name, public=False,
                        description=format_playlist_description("Discovery", period=str(current_year), playlist_type="discovery"))
                    valid_disc = [u for u in disc_uris if u and isinstance(u, str)]
                    for chunk in _chunked(valid_disc, 50):
                        if chunk:
                            api_call(sp.playlist_add_items, pl["id"], chunk)
                    _update_playlist_description_with_genres(sp, user_id, pl["id"], disc_uris)
                    _invalidate_playlist_cache()
                    log(f"  {disc_name}: created with {len(disc_uris)} tracks")
        else:
            log("  No streaming history for current year; skipping Top/Discovery update")
    else:
        log("  No streaming history; skipping Top/Discovery update")


# ============================================================================
# DUPLICATE PLAYLIST DETECTION & DELETION
# ============================================================================


