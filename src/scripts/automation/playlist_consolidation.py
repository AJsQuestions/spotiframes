"""
Playlist consolidation utilities.

Functions for consolidating old monthly playlists into yearly playlists
and cleaning up duplicate playlists.

This module is extracted from sync.py and uses late imports to access
utilities from sync.py to avoid circular dependencies.
"""

import os
import spotipy
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

from .formatting import format_playlist_name, format_yearly_playlist_name, format_playlist_description
from .error_handling import handle_errors

@handle_errors(reraise=False, default_return=None, log_error=True)
def consolidate_old_monthly_playlists(sp: spotipy.Spotify, keep_last_n_months: int = 3) -> None:
    """Merge old monthly playlists into yearly playlists, then delete the monthlies.
    
    When a month rolls out of the "keep last N" window (e.g. Jan ends, N=3: keep Dec, Jan, Feb):
    - For each old month (e.g. Nov): merge that month's playlist (e.g. AJFndsNov25) into the
      yearly playlist (e.g. AJFinds25) by adding its tracks to the yearly; then delete the
      monthly playlist. Tracks are never dropped—they move into the yearly.
    - Only the last N months (by calendar) remain as monthly playlists.
    
    For any months older than the last N:
    - Add all tracks from each old monthly playlist into the corresponding yearly playlist
    - Delete the old monthly playlist only after verifying its tracks are in the yearly
    
    Data Sources:
    - "Finds" playlists: Use API data (liked songs) - always up-to-date
    - Top and Discovery playlists: Use streaming history from exports (Vibes/OnRepeat removed)
      - Creates yearly playlists for ALL years with streaming history data
      - Streaming history may be incomplete for recent months (exports lag behind API)
      - Missing history for a year results in empty playlists for those types
    
    Args:
        keep_last_n_months: Number of recent months to keep as monthly playlists (default: 3)
    
    Note: This function only ADDS tracks to existing yearly playlists. It never removes tracks.
    Manually added tracks are preserved and will remain in the playlists.
    """
    # Late imports from sync.py
    from .sync import (
        log, verbose_log, DATA_DIR, OWNER_NAME, MONTH_NAMES,
        PREFIX_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY,
        ENABLE_MONTHLY, ENABLE_MOST_PLAYED, ENABLE_DISCOVERY,
        LIKED_SONGS_PLAYLIST_ID, YEARLY_NAME_TEMPLATE,
        get_existing_playlists, get_user_info, get_playlist_tracks,
        get_most_played_tracks, get_discovery_tracks,
        api_call,
        _chunked, _to_uri, _update_playlist_description_with_genres, _invalidate_playlist_cache,
    )
    log("\n--- Ensure yearly archive playlists ---")
    
    # Calculate cutoff date (keep last N months)
    # We want to keep the last N months, so anything at or before (current - N months) should be consolidated
    # Example: If current is Jan 2026 and N=3, keep Nov 2025, Dec 2025, Jan 2026
    # So cutoff should be Oct 2025 (last month to consolidate)
    cutoff_date = datetime.now() - relativedelta(months=keep_last_n_months)
    cutoff_year_month = cutoff_date.strftime("%Y-%m")
    
    # Get all existing playlists (cached)
    existing = get_existing_playlists(sp)
    user = get_user_info(sp)
    user_id = user["id"]
    
    # Pattern: {owner}{prefix}{mon}{year} e.g., "AJFindsJan23", "AJTopJan23", etc.
    # Extract monthly playlists matching patterns for enabled playlist types only
    # NOTE: Only monthly (Finds), Top, and Discovery are kept for yearly consolidation
    playlist_types = {}
    if ENABLE_MONTHLY:
        playlist_types["monthly"] = PREFIX_MONTHLY
    if ENABLE_MOST_PLAYED:
        playlist_types["most_played"] = PREFIX_MOST_PLAYED
    # Vibes/OnRepeat removed - only Top and Discovery kept for yearly
    # if ENABLE_TIME_BASED:
    #     playlist_types["time_based"] = PREFIX_TIME_BASED
    # if ENABLE_REPEAT:
    #     playlist_types["repeat"] = PREFIX_REPEAT
    if ENABLE_DISCOVERY:
        playlist_types["discovery"] = PREFIX_DISCOVERY
    
    monthly_playlists = {}  # {year: {type: [(name, id), ...]}}
    
    for playlist_name, playlist_id in existing.items():
        # Check each playlist type
        for playlist_type, prefix in playlist_types.items():
            monthly_pattern = f"{OWNER_NAME}{prefix}"
            if playlist_name.startswith(monthly_pattern):
                # Check if it matches monthly format (has a month name)
                for mon_abbr in MONTH_NAMES.values():
                    if playlist_name.startswith(f"{monthly_pattern}{mon_abbr}"):
                        # Extract year (2 or 4 digits at the end)
                        remaining = playlist_name[len(f"{monthly_pattern}{mon_abbr}"):]
                        if remaining.isdigit():
                            year_str = remaining
                            # Convert 2-digit year to 4-digit (assume 2000s)
                            if len(year_str) == 2:
                                year = 2000 + int(year_str)
                            else:
                                year = int(year_str)
                            
                            # Find the month number from abbreviation
                            month_num = None
                            for num, abbr in MONTH_NAMES.items():
                                if abbr == mon_abbr:
                                    month_num = num
                                    break
                            
                            if month_num:
                                # Create YYYY-MM format string
                                month_str = f"{year}-{month_num}"
                                
                                # Check if this month is at or before cutoff (should be consolidated)
                                # Use <= to include the cutoff month itself
                                if month_str <= cutoff_year_month:
                                    if year not in monthly_playlists:
                                        monthly_playlists[year] = {}
                                    if playlist_type not in monthly_playlists[year]:
                                        monthly_playlists[year][playlist_type] = []
                                    monthly_playlists[year][playlist_type].append((playlist_name, playlist_id))
                        break
                break  # Found matching type, no need to check others
    
    # Load liked songs data to get tracks by year (for "Finds" playlists)
    year_to_tracks = {}
    try:
        playlist_tracks_path = DATA_DIR / "playlist_tracks.parquet"
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
                    liked["year"] = liked[added_col].dt.year
                    
                    # Handle both track_uri and track_id columns
                    if "track_uri" in liked.columns:
                        liked["_uri"] = liked["track_uri"]
                    else:
                        liked["_uri"] = liked["track_id"].map(_to_uri)
                    
                    # Build year -> tracks mapping (only for months at or before cutoff)
                    liked["year_month"] = liked[added_col].dt.to_period("M").astype(str)
                    for year_month, group in liked.groupby("year_month"):
                        if year_month <= cutoff_year_month:
                            year = int(year_month.split("-")[0])
                            uris = group["_uri"].dropna().tolist()
                            # Deduplicate while preserving order
                            seen = set()
                            unique = [u for u in uris if not (u in seen or seen.add(u))]
                            if year not in year_to_tracks:
                                year_to_tracks[year] = []
                            year_to_tracks[year].extend(unique)
                    
                    # Deduplicate tracks per year
                    for year in year_to_tracks:
                        seen = set()
                        year_to_tracks[year] = [u for u in year_to_tracks[year] if not (u in seen or seen.add(u))]
    except Exception as e:
        log(f"  ⚠️  Could not load liked songs data: {e}")
    
    # Load streaming history for Top and Discovery playlists (Vibes/OnRepeat removed from yearly)
    # NOTE: Streaming history comes from periodic Spotify exports and may lag behind API data.
    # This is used for creating yearly playlists for previous years.
    # Missing or incomplete history will result in empty playlists for those years.
    from src.analysis.streaming_history import load_streaming_history
    history_df = load_streaming_history(DATA_DIR)
    year_to_tracks_history = {}  # {year: {type: [uris]}}
    
    if history_df is not None and not history_df.empty:
        try:
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'], errors='coerce', utc=True)
            history_df['year'] = history_df['timestamp'].dt.year
            history_df['year_month'] = history_df['timestamp'].dt.to_period('M').astype(str)
            
            # Get track URI column
            track_col = None
            if 'track_uri' in history_df.columns:
                track_col = 'track_uri'
            elif 'spotify_track_uri' in history_df.columns:
                track_col = 'spotify_track_uri'
            
            if track_col:
                # Get ALL years from streaming history (not just old months)
                # Top/Dscvr are created as yearly playlists only (no monthly). Vbz/Rpt removed.
                for year in history_df['year'].unique():
                    year_data = history_df[history_df['year'] == year].copy()
                    if year not in year_to_tracks_history:
                        year_to_tracks_history[year] = {}
                    
                    # Most played tracks for the year - KEPT for yearly playlists
                    top_tracks = get_most_played_tracks(year_data, None, limit=100)
                    if top_tracks:
                        year_to_tracks_history[year]['most_played'] = top_tracks
                    
                    # Repeat tracks removed - OnRepeat no longer supported
                    # repeat_tracks = get_repeat_tracks(year_data, None, min_repeats=3, limit=100)
                    # if repeat_tracks:
                    #     year_to_tracks_history[year]['repeat'] = repeat_tracks
                    
                    # Discovery tracks (first time played in this year) - KEPT for yearly playlists
                    discovery_tracks = get_discovery_tracks(year_data, None, limit=100)
                    if discovery_tracks:
                        year_to_tracks_history[year]['discovery'] = discovery_tracks
                    
                    # Time-based tracks removed - Vibes no longer in yearly playlists
                    # time_tracks = get_time_based_tracks(year_data, None, time_type="evening", limit=100)
                    # if time_tracks:
                    #     year_to_tracks_history[year]['time_based'] = time_tracks
        except Exception as e:
            log(f"  ⚠️  Could not process streaming history for consolidation: {e}")
    
    # Consolidate years that have:
    # 1. Monthly playlists that need consolidation (for "Finds" only), OR
    # 2. Streaming history data (for Dscvr - yearly only), OR
    # 3. Liked songs data (for Finds - yearly)
    # NOTE: Dscvr is created as yearly playlists only (no monthly). Top/Vbz/Rpt removed.
    years_to_consolidate = set()
    
    # Get all years from all data sources
    all_years = set(monthly_playlists.keys()) | set(year_to_tracks.keys()) | set(year_to_tracks_history.keys())
    
    # Check which years need consolidation (for all playlist types)
    for year in sorted(all_years):
        year_short = str(year)[2:] if len(str(year)) == 4 else str(year)
        needs_consolidation = False
        
        # Check if "Finds" monthly playlists need consolidation
        if year in monthly_playlists and monthly_playlists[year]:
            needs_consolidation = True
        
        # Check if yearly playlists need to be created for Top and Discovery (Vbz/Rpt removed)
        # Top and Discovery are created as yearly playlists only (no monthly)
        if year in year_to_tracks_history:
            for playlist_type in ["most_played", "discovery"]:  # Top and Discovery kept for yearly
                if playlist_type in year_to_tracks_history[year]:
                    # Check if this playlist type is enabled
                    if (playlist_type == "most_played" and ENABLE_MOST_PLAYED) or \
                       (playlist_type == "discovery" and ENABLE_DISCOVERY):
                        # Check if yearly playlist exists
                        yearly_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type=playlist_type)
                        if yearly_name not in existing:
                            needs_consolidation = True
                            break
        
        # Check if "Finds" yearly playlist needs to be created (from liked songs data)
        if year in year_to_tracks and year_to_tracks[year]:
            yearly_name = format_yearly_playlist_name(str(year))
            if yearly_name not in existing:
                needs_consolidation = True
        
        if needs_consolidation:
            years_to_consolidate.add(year)
    
    if not years_to_consolidate:
        log("  No old years need consolidation (all already consolidated)")
        return
    
    log(f"  Found {len(years_to_consolidate)} year(s) to consolidate: {sorted(years_to_consolidate)}")
    
    # Log which data sources are available for each year
    for year in sorted(years_to_consolidate):
        sources = []
        if year in monthly_playlists:
            sources.append(f"{len(monthly_playlists[year])} monthly playlist(s)")
        if year in year_to_tracks:
            sources.append("liked songs data")
        if year in year_to_tracks_history:
            enabled_types = [t for t in year_to_tracks_history[year].keys() if t in playlist_types]
            if enabled_types:
                sources.append(f"streaming history ({', '.join(enabled_types)})")
        if sources:
            log(f"    {year}: {', '.join(sources)}")
    
    # For each old year, consolidate into yearly playlists for each type
    for year in sorted(years_to_consolidate):
        year_short = str(year)[2:] if len(str(year)) == 4 else str(year)
        
        # Process each playlist type
        for playlist_type, prefix in playlist_types.items():
            # Collect all tracks for this year and type
            # Use list to preserve ordering for "Top" and other ordered playlists
            all_tracks_list = []
            all_tracks_set = set()  # For deduplication
            
            # First, try to get tracks from existing monthly playlists of this type
            if year in monthly_playlists and playlist_type in monthly_playlists[year]:
                for monthly_name, monthly_id in monthly_playlists[year][playlist_type]:
                    tracks = get_playlist_tracks(sp, monthly_id)
                    # Preserve order from playlist (playlists are already ordered)
                    for track in tracks:
                        if track not in all_tracks_set:
                            all_tracks_list.append(track)
                            all_tracks_set.add(track)
                    log(f"    - {monthly_name}: {len(tracks)} tracks")
            
            # If no tracks from playlists, use appropriate data source
            if not all_tracks_list:
                if playlist_type == "monthly" and year in year_to_tracks:
                    # Use liked songs data for "Finds" playlists
                    for track in year_to_tracks[year]:
                        if track not in all_tracks_set:
                            all_tracks_list.append(track)
                            all_tracks_set.add(track)
                    log(f"    - Using liked songs data for {playlist_type}: {len(year_to_tracks[year])} tracks")
                elif playlist_type in ["most_played", "discovery"]:  # Top and Discovery kept (time_based/repeat removed)
                    # Use streaming history data (already sorted)
                    if year in year_to_tracks_history and playlist_type in year_to_tracks_history[year]:
                        # These are already sorted by the get_*_tracks functions
                        for track in year_to_tracks_history[year][playlist_type]:
                            if track not in all_tracks_set:
                                all_tracks_list.append(track)
                                all_tracks_set.add(track)
                        log(f"    - Using streaming history for {playlist_type}: {len(year_to_tracks_history[year][playlist_type])} tracks")
            
            # Re-sort tracks by play count if we got them from monthly playlists
            # Note: If tracks came from year_to_tracks_history, they're already sorted, so we skip re-sorting
            tracks_from_monthly = year in monthly_playlists and playlist_type in monthly_playlists.get(year, {})
            if all_tracks_list and playlist_type in ["most_played", "discovery"] and tracks_from_monthly:
                # If we have streaming history for this year, re-sort by actual play counts
                if history_df is not None and not history_df.empty:
                    try:
                        # Filter to this year's data
                        year_data = history_df[history_df['year'] == year].copy()
                        if not year_data.empty:
                            # Get track URI column
                            track_col = None
                            if 'track_uri' in year_data.columns:
                                track_col = 'track_uri'
                            elif 'spotify_track_uri' in year_data.columns:
                                track_col = 'spotify_track_uri'
                            
                            if track_col:
                                # Calculate play counts for all tracks
                                track_stats = year_data.groupby(track_col).agg({
                                    'ms_played': ['count', 'sum']
                                }).reset_index()
                                track_stats.columns = ['track_uri', 'play_count', 'total_ms']
                                
                                # Create a mapping of track URI to play count
                                play_count_map = dict(zip(track_stats['track_uri'], track_stats['play_count']))
                                
                                # Sort tracks by play count (most played first)
                                # Tracks not in history get play_count = 0
                                if playlist_type == "most_played":
                                    all_tracks_list.sort(
                                        key=lambda uri: (play_count_map.get(uri, 0), 0),
                                        reverse=True
                                    )
                                    log(f"    - Re-sorted {playlist_type} tracks by play count")
                                # Discovery tracks are already sorted by first play time (most recent first)
                                # from get_discovery_tracks, so we keep that order
                    except Exception as e:
                        log(f"    ⚠️  Could not re-sort tracks by play count: {e}")
                        # Continue with existing order if sorting fails
            
            if not all_tracks_list:
                log(f"    ⚠️  No tracks found for {year} ({playlist_type}), skipping")
                continue
            
            # Create yearly playlist for this type
            if playlist_type == "monthly":
                main_playlist_name = format_yearly_playlist_name(str(year))
                playlist_configs = [(main_playlist_name, "All tracks", None)]
            else:
                # For other types, create single yearly playlist
                # Use yearly template format (no month) for yearly playlists
                # The templates default to monthly format, so we use YEARLY_NAME_TEMPLATE as base
                # but with the appropriate prefix for each type
                yearly_name = format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type=playlist_type)
                playlist_configs = [
                    (yearly_name, f"{playlist_type.replace('_', ' ').title()} tracks", None),
                ]
            
            for playlist_name, description, genre_filter in playlist_configs:
                filtered_tracks = all_tracks_list
                if not filtered_tracks:
                    log(f"    ⚠️  No tracks for {year}, skipping {playlist_name}")
                    continue
                # Create or update playlist
                if playlist_name in existing:
                    # If we're not consolidating from monthly playlists (they were already deleted),
                    # and the playlist already exists, skip the expensive check
                    if year not in monthly_playlists:
                        log(f"  {playlist_name}: already consolidated (skipping check)")
                        continue
                    pid = existing[playlist_name]
                    already = get_playlist_tracks(sp, pid)
                    to_add = [u for u in filtered_tracks if u and isinstance(u, str) and u not in already]
                    if to_add:
                        for chunk in _chunked(to_add, 50):
                            valid = [u for u in chunk if u and isinstance(u, str)]
                            if valid:
                                api_call(sp.playlist_add_items, pid, valid)
                        log(f"  {playlist_name}: +{len(to_add)} tracks (total: {len(filtered_tracks)}; manually added tracks preserved)")
                        _update_playlist_description_with_genres(sp, user_id, pid, None)
                    else:
                        log(f"  {playlist_name}: already up to date ({len(filtered_tracks)} tracks)")
                        _update_playlist_description_with_genres(sp, user_id, pid, None)
                else:
                    pl = api_call(
                        sp.user_playlist_create,
                        user_id,
                        playlist_name,
                        public=False,
                        description=format_playlist_description(description, period=str(year), playlist_type=playlist_type),
                    )
                    pid = pl["id"]
                    valid_tracks = [u for u in filtered_tracks if u and isinstance(u, str)]
                    for chunk in _chunked(valid_tracks, 50):
                        if chunk:
                            api_call(sp.playlist_add_items, pid, chunk)
                    _update_playlist_description_with_genres(sp, user_id, pid, valid_tracks)
                    log(f"  {playlist_name}: created with {len(valid_tracks)} tracks")
                # Delete old monthly playlists if they existed (with verification)
                if year in monthly_playlists and playlist_type in monthly_playlists[year]:
                    final_yearly_tracks = get_playlist_tracks(sp, pid, force_refresh=True)
                    for monthly_name, monthly_id in monthly_playlists[year][playlist_type]:
                        try:
                            monthly_tracks = get_playlist_tracks(sp, monthly_id, force_refresh=True)
                            missing_tracks = monthly_tracks - final_yearly_tracks
                            if missing_tracks:
                                log(f"    ⚠️  WARNING: {len(missing_tracks)} tracks from '{monthly_name}' are NOT in yearly playlist!")
                                continue
                            from .data_protection import safe_delete_playlist
                            success, backup_file = safe_delete_playlist(
                                sp, monthly_id, monthly_name,
                                create_backup=True,
                                verify_tracks_preserved_in=pid
                            )
                            if success:
                                _invalidate_playlist_cache()
                                log(f"    ✓ Deleted {monthly_name} ({len(monthly_tracks)} tracks verified)")
                            elif backup_file:
                                log(f"    💾 Backup created: {backup_file.name}")
                        except Exception as e:
                            log(f"    ⚠️  Failed to delete {monthly_name}: {e}")
        log(f"  ✅ Consolidated {year} into yearly playlists for all types")




def delete_old_monthly_playlists(sp: spotipy.Spotify) -> None:
    """No-op: superseded by delete_automated_monthly_and_genre_playlists."""
    from .sync import log
    log("\n--- Deleting Old Monthly Playlists (no-op) ---")


def _is_automated_monthly_playlist(name: str, owner: str, prefixes: list, month_abbrs: list) -> bool:
    """True if name matches {owner}{prefix}{month}{year} e.g. AJFindsJan26."""
    if not name or not name.startswith(owner):
        return False
    suffix = name[len(owner):]
    for prefix in prefixes:
        if suffix.startswith(prefix):
            rest = suffix[len(prefix):]
            for abbr in month_abbrs:
                if rest.startswith(abbr) and len(rest) > len(abbr) and rest[len(abbr):].isdigit():
                    return True
    return False


def _is_automated_genre_playlist(name: str, owner: str) -> bool:
    """True if name looks like an automated genre playlist (HipHop, Dance, Other, or AJAm master)."""
    if not name or not name.startswith(owner):
        return False
    rest = name[len(owner):]
    # Old genre split: prefix + HipHop/Dance/Other + year, or master "Am" + genre
    genre_slugs = ("HipHop", "Hip Hop", "Dance", "Other", "Am")
    return any(s in rest for s in genre_slugs)


@handle_errors(reraise=False, default_return=None, log_error=True)
def delete_automated_monthly_and_genre_playlists(sp: spotipy.Spotify) -> None:
    """Delete all automated monthly playlists and all genre automated playlists.
    Keeps only yearly Finds, Top, Discovery playlists. Uses backups before deletion.
    """
    from .sync import (
        log, verbose_log, OWNER_NAME, MONTH_NAMES,
        PREFIX_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY,
        get_existing_playlists, _invalidate_playlist_cache,
    )
    from .data_protection import safe_delete_playlist
    from .formatting import format_yearly_playlist_name, format_playlist_name
    from .config import YEARLY_NAME_TEMPLATE

    log("\n--- Cleanup legacy automated playlists ---")
    existing = get_existing_playlists(sp, force_refresh=True)
    owner = OWNER_NAME
    prefixes = [PREFIX_MONTHLY, PREFIX_MOST_PLAYED, PREFIX_DISCOVERY]
    month_abbrs = list(MONTH_NAMES.values())

    to_delete = []
    yearly_names = set()
    current_year = datetime.now().year
    for year in range(2015, current_year + 2):
        yearly_names.add(format_yearly_playlist_name(str(year)))
        year_short = str(year)[2:] if year >= 2000 else str(year)
        yearly_names.add(format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="most_played"))
        yearly_names.add(format_playlist_name(YEARLY_NAME_TEMPLATE, year=year_short, playlist_type="discovery"))

    for playlist_name, playlist_id in list(existing.items()):
        if not playlist_name.startswith(owner):
            continue
        if playlist_name in yearly_names:
            continue
        if _is_automated_monthly_playlist(playlist_name, owner, prefixes, month_abbrs):
            to_delete.append((playlist_name, playlist_id))
        elif _is_automated_genre_playlist(playlist_name, owner):
            to_delete.append((playlist_name, playlist_id))

    if not to_delete:
        log("  No legacy automated playlists to delete.")
        return

    log(f"  Found {len(to_delete)} legacy playlist(s) to delete.")
    deleted = 0
    for playlist_name, playlist_id in to_delete:
        try:
            success, backup_file = safe_delete_playlist(
                sp, playlist_id, playlist_name,
                create_backup=True,
                verify_tracks_preserved_in=None,
            )
            if success:
                _invalidate_playlist_cache()
                log(f"  Deleted: {playlist_name}")
                deleted += 1
            elif backup_file:
                log(f"  Backup: {backup_file.name} (delete skipped or failed)")
        except Exception as e:
            log(f"  Failed to delete {playlist_name}: {e}")
    log(f"  Done. Deleted {deleted} playlist(s).")




def delete_duplicate_playlists(sp: spotipy.Spotify) -> None:
    """Delete duplicate playlists based on track content (same tracks, different names).
    
    Compares all playlists and identifies duplicates by checking if they have
    the same set of tracks. Keeps the first playlist (by name) and deletes others.
    """
    # Late imports from sync.py
    from .sync import (
        log, get_existing_playlists, get_user_info, get_playlist_tracks,
        api_call, _invalidate_playlist_cache
    )
    log("\n--- Detecting and Deleting Duplicate Playlists ---")
    
    existing = get_existing_playlists(sp, force_refresh=True)
    user = get_user_info(sp)
    user_id = user["id"]
    
    if not existing:
        log("  ℹ️  No playlists found")
        return
    
    log(f"  Checking {len(existing)} playlist(s) for duplicates...")
    
    # Limit duplicate checking to reasonable number of playlists to avoid timeout
    # Focus on playlists that might be duplicates (similar names or automated playlists)
    # Allow override via environment variable
    max_playlists = int(os.environ.get("MAX_PLAYLISTS_FOR_DUPLICATE_CHECK", "1000"))
    if len(existing) > max_playlists:
        log(f"  ⚠️  Too many playlists ({len(existing):,}) - skipping duplicate detection")
        log(f"      Set MAX_PLAYLISTS_FOR_DUPLICATE_CHECK env var to override (current limit: {max_playlists})")
        return
    
    # Build track set for each playlist
    playlist_track_sets = {}
    checked = 0
    for name, playlist_id in existing.items():
        try:
            tracks = get_playlist_tracks(sp, playlist_id, force_refresh=False)  # Use cache if available
            # Convert to frozenset for comparison (order doesn't matter)
            track_set = frozenset(tracks)
            if track_set in playlist_track_sets:
                # Found a duplicate - add to the list
                playlist_track_sets[track_set].append((name, playlist_id))
            else:
                playlist_track_sets[track_set] = [(name, playlist_id)]
            checked += 1
            if checked % 50 == 0:
                log(f"  Progress: checked {checked}/{len(existing)} playlists...")
        except Exception as e:
            log(f"  ⚠️  Could not read tracks from '{name}': {e}")
            continue
    
    # Find duplicates (playlists with same track set)
    deleted_count = 0
    for track_set, playlists in playlist_track_sets.items():
        if len(playlists) > 1 and len(track_set) > 0:  # Only consider non-empty playlists
            # Sort by name to keep the first one (alphabetically)
            playlists_sorted = sorted(playlists, key=lambda x: x[0])
            keep_playlist = playlists_sorted[0]
            duplicates = playlists_sorted[1:]
            
            log(f"  🔍 Found {len(playlists)} duplicate playlist(s) with {len(track_set)} tracks:")
            log(f"     ✅ Keeping: '{keep_playlist[0]}'")
            
            for dup_name, dup_id in duplicates:
                try:
                    # Safe deletion with backup and verification
                    from .data_protection import safe_delete_playlist
                    # Verify tracks are preserved in the kept playlist
                    success, backup_file = safe_delete_playlist(
                        sp, dup_id, dup_name,
                        create_backup=True,
                        verify_tracks_preserved_in=keep_playlist[1]  # Verify in kept playlist
                    )
                    if success:
                        log(f"     🗑️  Deleted: '{dup_name}'")
                        deleted_count += 1
                        # Remove from cache
                        _invalidate_playlist_cache()
                        if dup_name in existing:
                            del existing[dup_name]
                    else:
                        log(f"     ⚠️  Skipped deletion of '{dup_name}' (safety check failed)")
                        if backup_file:
                            log(f"     💾 Backup created: {backup_file.name}")
                except Exception as e:
                    log(f"     ⚠️  Failed to delete '{dup_name}': {e}")
    
    if deleted_count > 0:
        log(f"  ✅ Deleted {deleted_count} duplicate playlist(s)")
    else:
        log("  ℹ️  No duplicate playlists found")


# ============================================================================
# MAIN
# ============================================================================


