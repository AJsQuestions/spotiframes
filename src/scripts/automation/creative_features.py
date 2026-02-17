"""
Creative Playlist Features

Advanced features for playlist creation and management:
- Theme-based playlist generation
- Mood-based organization
- Time-capsule playlists
- Smart playlist mixing
"""

import spotipy
import pandas as pd
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from collections import Counter
import random

from .sync import DATA_DIR, log, verbose_log, get_existing_playlists, get_user_info, api_call


def generate_theme_playlist(
    sp: spotipy.Spotify,
    theme: str,
    track_count: int = 50,
    seed_tracks: Optional[List[str]] = None
) -> Optional[str]:
    """
    Generate a playlist based on a theme.
    
    Themes:
    - "workout": High-energy tracks
    - "study": Focused, instrumental tracks
    - "chill": Relaxed, ambient tracks
    - "party": Upbeat, dance tracks
    - "roadtrip": Varied, long-form tracks
    
    Args:
        theme: Theme name
        track_count: Number of tracks to include
        seed_tracks: Optional seed tracks for recommendations
    
    Returns:
        Playlist ID if created, None otherwise
    """
    user = get_user_info(sp)
    user_id = user["id"]
    
    theme_configs = {
        "workout": {
            "name": "💪 Workout Mix",
            "description": "High-energy tracks to power your workout",
            "target_genres": ["Hip-Hop", "Electronic", "Dance", "Rock"],
            "min_energy": 0.7,
            "min_tempo": 120
        },
        "study": {
            "name": "📚 Study Focus",
            "description": "Instrumental and ambient tracks for concentration",
            "target_genres": ["Classical", "Jazz", "Electronic", "Ambient"],
            "max_energy": 0.5,
            "instrumental_preference": True
        },
        "chill": {
            "name": "🌙 Chill Vibes",
            "description": "Relaxed tracks for unwinding",
            "target_genres": ["R&B/Soul", "Jazz", "Indie", "Folk"],
            "max_energy": 0.6,
            "max_tempo": 100
        },
        "party": {
            "name": "🎉 Party Mix",
            "description": "Upbeat tracks to get the party started",
            "target_genres": ["Dance", "Electronic", "Hip-Hop", "Pop"],
            "min_energy": 0.7,
            "min_tempo": 110
        },
        "roadtrip": {
            "name": "🛣️ Road Trip",
            "description": "Varied tracks for long drives",
            "target_genres": ["Rock", "Pop", "Country/Folk", "Hip-Hop"],
            "variety_preference": True
        }
    }
    
    if theme not in theme_configs:
        log(f"  ⚠️  Unknown theme: {theme}")
        return None
    
    config = theme_configs[theme]
    
    # Load library data
    try:
        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
        artists_df = pd.read_parquet(DATA_DIR / "artists.parquet")
    except Exception as e:
        log(f"  ⚠️  Could not load data: {e}")
        return None
    
    # Get liked songs
    from .sync import LIKED_SONGS_PLAYLIST_ID
    liked_tracks = playlist_tracks_df[
        playlist_tracks_df["playlist_id"] == LIKED_SONGS_PLAYLIST_ID
    ]
    
    if liked_tracks.empty:
        log(f"  ⚠️  No liked songs found")
        return None
    
    # Filter tracks by theme criteria
    merged = liked_tracks.merge(tracks_df, on="track_id", how="left")
    
    # Filter by genre if specified
    if "target_genres" in config:
        # Get genres for tracks
        track_artists_df = pd.read_parquet(DATA_DIR / "track_artists.parquet")
        artist_genres_map = artists_df.set_index("artist_id")["genres"].to_dict()
        
        matching_tracks = []
        for _, row in merged.iterrows():
            track_id = row["track_id"]
            # Get genres from track or artists
            track_genres = []
            if "genres" in row and pd.notna(row["genres"]):
                if isinstance(row["genres"], list):
                    track_genres = row["genres"]
            
            # Also check artist genres
            track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
            for _, ta_row in track_artists.iterrows():
                artist_id = ta_row["artist_id"]
                if artist_id in artist_genres_map:
                    artist_genres = artist_genres_map[artist_id]
                    if isinstance(artist_genres, list):
                        track_genres.extend(artist_genres)
            
            # Check if matches target genres (use raw artist/track genres)
            if any(genre in config["target_genres"] for genre in track_genres):
                matching_tracks.append(row)
        
        if matching_tracks:
            merged = pd.DataFrame(matching_tracks)
        else:
            log(f"  ⚠️  No tracks match theme criteria")
            return None
    
    # Select tracks
    selected = merged.sample(min(track_count, len(merged)))
    
    # Create playlist
    existing = get_existing_playlists(sp)
    playlist_name = config["name"]
    
    if playlist_name in existing:
        log(f"  ℹ️  Playlist '{playlist_name}' already exists")
        return existing[playlist_name]
    
    pl = api_call(
        sp.user_playlist_create,
        user_id,
        playlist_name,
        public=False,
        description=config["description"]
    )
    
    playlist_id = pl["id"]
    
    # Add tracks
    track_uris = [f"spotify:track:{tid}" for tid in selected["track_id"]]
    from .sync import _chunked
    for chunk in _chunked(track_uris, 50):
        api_call(sp.playlist_add_items, playlist_id, chunk)
    
    log(f"  ✅ Created '{playlist_name}' with {len(track_uris)} tracks")
    return playlist_id


def create_time_capsule_playlist(
    sp: spotipy.Spotify,
    year: int,
    track_count: int = 50
) -> Optional[str]:
    """
    Create a "time capsule" playlist of tracks from a specific year.
    
    Args:
        year: Year to create playlist for
        track_count: Number of tracks to include
    
    Returns:
        Playlist ID if created, None otherwise
    """
    user = get_user_info(sp)
    user_id = user["id"]
    
    try:
        tracks_df = pd.read_parquet(DATA_DIR / "tracks.parquet")
        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    except Exception as e:
        log(f"  ⚠️  Could not load data: {e}")
        return None
    
    # Get liked songs
    from .sync import LIKED_SONGS_PLAYLIST_ID
    liked_tracks = playlist_tracks_df[
        playlist_tracks_df["playlist_id"] == LIKED_SONGS_PLAYLIST_ID
    ]
    
    # Filter by year
    merged = liked_tracks.merge(tracks_df, on="track_id", how="left")
    
    if "release_year" in merged.columns:
        year_tracks = merged[merged["release_year"] == year]
    else:
        log(f"  ⚠️  No release year data available")
        return None
    
    if year_tracks.empty:
        log(f"  ⚠️  No tracks found from {year}")
        return None
    
    # Select tracks
    selected = year_tracks.sample(min(track_count, len(year_tracks)))
    
    # Create playlist
    existing = get_existing_playlists(sp)
    playlist_name = f"📅 {year} Time Capsule"
    
    if playlist_name in existing:
        log(f"  ℹ️  Playlist '{playlist_name}' already exists")
        return existing[playlist_name]
    
    pl = api_call(
        sp.user_playlist_create,
        user_id,
        playlist_name,
        public=False,
        description=f"Tracks from {year} - a musical time capsule"
    )
    
    playlist_id = pl["id"]
    
    # Add tracks
    track_uris = [f"spotify:track:{tid}" for tid in selected["track_id"]]
    from .sync import _chunked
    for chunk in _chunked(track_uris, 50):
        api_call(sp.playlist_add_items, playlist_id, chunk)
    
    log(f"  ✅ Created '{playlist_name}' with {len(track_uris)} tracks from {year}")
    return playlist_id


def create_on_this_day_playlist(
    sp: spotipy.Spotify,
    date: Optional[datetime] = None,
    years_ago: int = 1
) -> Optional[str]:
    """
    Create a playlist of tracks you were listening to "on this day" X years ago.
    
    Args:
        date: Specific date (defaults to today)
        years_ago: How many years ago to look back
    
    Returns:
        Playlist ID if created, None otherwise
    """
    if date is None:
        date = datetime.now()
    
    target_date = date - timedelta(days=365 * years_ago)
    
    try:
        streaming_history_df = pd.read_parquet(DATA_DIR / "streaming_history.parquet")
    except Exception:
        log(f"  ⚠️  Streaming history not available")
        return None
    
    if streaming_history_df.empty:
        log(f"  ⚠️  No streaming history data")
        return None
    
    # Filter to target date range (same month/day, different year)
    if "timestamp" in streaming_history_df.columns:
        streaming_history_df["date"] = pd.to_datetime(streaming_history_df["timestamp"]).dt.date
        target_month_day = (target_date.month, target_date.day)
        
        # Get tracks from same month/day in previous years
        matching = streaming_history_df[
            streaming_history_df["date"].apply(
                lambda d: (d.month, d.day) == target_month_day
            )
        ]
        
        if matching.empty:
            log(f"  ⚠️  No listening data for {target_date.strftime('%B %d')}")
            return None
        
        # Get most played tracks from that date
        if "track_uri" in matching.columns:
            track_col = "track_uri"
        elif "spotify_track_uri" in matching.columns:
            track_col = "spotify_track_uri"
        else:
            log(f"  ⚠️  No track URI column found")
            return None
        
        top_tracks = matching[track_col].value_counts().head(50).index.tolist()
        
        # Create playlist
        user = get_user_info(sp)
        user_id = user["id"]
        existing = get_existing_playlists(sp)
        
        playlist_name = f"📆 On This Day {years_ago} Year{'s' if years_ago > 1 else ''} Ago"
        
        if playlist_name in existing:
            log(f"  ℹ️  Playlist '{playlist_name}' already exists")
            return existing[playlist_name]
        
        pl = api_call(
            sp.user_playlist_create,
            user_id,
            playlist_name,
            public=False,
            description=f"What you were listening to on {target_date.strftime('%B %d')} {years_ago} year{'s' if years_ago > 1 else ''} ago"
        )
        
        playlist_id = pl["id"]
        
        # Add tracks
        from .sync import _chunked
        for chunk in _chunked(top_tracks, 50):
            api_call(sp.playlist_add_items, playlist_id, chunk)
        
        log(f"  ✅ Created '{playlist_name}' with {len(top_tracks)} tracks")
        return playlist_id
    
    return None


def smart_mix_playlists(
    sp: spotipy.Spotify,
    playlist_names: List[str],
    new_playlist_name: str,
    mix_strategy: str = "balanced"
) -> Optional[str]:
    """
    Intelligently mix multiple playlists.
    
    Strategies:
    - "balanced": Equal representation from each playlist
    - "weighted": Weight by playlist size
    - "shuffled": Random mix
    - "chronological": By track addition date
    
    Returns:
        Playlist ID if created, None otherwise
    """
    user = get_user_info(sp)
    user_id = user["id"]
    
    try:
        playlists_df = pd.read_parquet(DATA_DIR / "playlists.parquet")
        playlist_tracks_df = pd.read_parquet(DATA_DIR / "playlist_tracks.parquet")
    except Exception as e:
        log(f"  ⚠️  Could not load data: {e}")
        return None
    
    # Find playlists
    playlist_ids = []
    for name in playlist_names:
        matches = playlists_df[playlists_df["name"] == name]
        if not matches.empty:
            playlist_ids.append(matches.iloc[0]["playlist_id"])
        else:
            log(f"  ⚠️  Playlist '{name}' not found")
    
    if not playlist_ids:
        log(f"  ⚠️  No valid playlists found")
        return None
    
    # Get tracks from all playlists
    all_tracks = []
    playlist_track_counts = {}
    
    for pid in playlist_ids:
        tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == pid]
        track_list = tracks["track_id"].unique().tolist()
        playlist_track_counts[pid] = len(track_list)
        all_tracks.extend([(tid, pid) for tid in track_list])
    
    # Remove duplicates (keep first occurrence)
    seen = set()
    unique_tracks = []
    for tid, pid in all_tracks:
        if tid not in seen:
            seen.add(tid)
            unique_tracks.append((tid, pid))
    
    # Apply mixing strategy
    if mix_strategy == "balanced":
        # Equal representation
        tracks_per_playlist = len(unique_tracks) // len(playlist_ids)
        selected = []
        for pid in playlist_ids:
            pid_tracks = [tid for tid, p in unique_tracks if p == pid]
            selected.extend(pid_tracks[:tracks_per_playlist])
    elif mix_strategy == "weighted":
        # Weight by playlist size
        total_tracks = sum(playlist_track_counts.values())
        selected = []
        for pid in playlist_ids:
            weight = playlist_track_counts[pid] / total_tracks
            count = int(len(unique_tracks) * weight)
            pid_tracks = [tid for tid, p in unique_tracks if p == pid]
            selected.extend(pid_tracks[:count])
    elif mix_strategy == "shuffled":
        # Random mix
        selected = [tid for tid, _ in unique_tracks]
        random.shuffle(selected)
    else:  # chronological
        # By addition date if available
        if "added_at" in playlist_tracks_df.columns:
            df = pd.DataFrame(unique_tracks, columns=["track_id", "playlist_id"])
            merged = df.merge(
                playlist_tracks_df[["track_id", "playlist_id", "added_at"]],
                on=["track_id", "playlist_id"],
                how="left"
            )
            merged = merged.sort_values("added_at")
            selected = merged["track_id"].tolist()
        else:
            selected = [tid for tid, _ in unique_tracks]
    
    # Create playlist
    existing = get_existing_playlists(sp)
    if new_playlist_name in existing:
        log(f"  ℹ️  Playlist '{new_playlist_name}' already exists")
        return existing[new_playlist_name]
    
    pl = api_call(
        sp.user_playlist_create,
        user_id,
        new_playlist_name,
        public=False,
        description=f"Smart mix of {len(playlist_names)} playlists ({mix_strategy} strategy)"
    )
    
    playlist_id = pl["id"]
    
    # Add tracks
    track_uris = [f"spotify:track:{tid}" for tid in selected]
    from .sync import _chunked
    for chunk in _chunked(track_uris, 50):
        api_call(sp.playlist_add_items, playlist_id, chunk)
    
    log(f"  ✅ Created '{new_playlist_name}' with {len(track_uris)} tracks")
    return playlist_id
