"""
Playlist Intelligence & Smart Features

Creative enhancements for playlist management including:
- Smart playlist recommendations
- Mood-based organization
- Listening pattern analysis
- Playlist similarity detection
- Auto-arrangement suggestions
"""

import spotipy
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import math

from .sync import DATA_DIR, log, verbose_log

def calculate_playlist_similarity(
    playlist1_tracks: Set[str],
    playlist2_tracks: Set[str]
) -> float:
    """
    Calculate Jaccard similarity between two playlists.
    
    Returns:
        Similarity score between 0.0 (no overlap) and 1.0 (identical)
    """
    if not playlist1_tracks or not playlist2_tracks:
        return 0.0
    
    intersection = len(playlist1_tracks & playlist2_tracks)
    union = len(playlist1_tracks | playlist2_tracks)
    
    return intersection / union if union > 0 else 0.0


def find_similar_playlists(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    threshold: float = 0.3
) -> List[Tuple[str, str, float]]:
    """
    Find playlists with similar track content.
    
    Args:
        threshold: Minimum similarity score (0.0-1.0)
    
    Returns:
        List of (playlist1_name, playlist2_name, similarity_score) tuples
    """
    # Build track sets for each playlist
    playlist_tracks = {}
    for _, row in playlists_df.iterrows():
        playlist_id = row["playlist_id"]
        tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
        playlist_tracks[playlist_id] = set(tracks["track_id"].unique())
    
    # Calculate similarities
    similar = []
    playlist_ids = list(playlist_tracks.keys())
    
    for i, pid1 in enumerate(playlist_ids):
        for pid2 in playlist_ids[i+1:]:
            similarity = calculate_playlist_similarity(
                playlist_tracks[pid1],
                playlist_tracks[pid2]
            )
            if similarity >= threshold:
                name1 = playlists_df[playlists_df["playlist_id"] == pid1]["name"].iloc[0]
                name2 = playlists_df[playlists_df["playlist_id"] == pid2]["name"].iloc[0]
                similar.append((name1, name2, similarity))
    
    # Sort by similarity (highest first)
    similar.sort(key=lambda x: x[2], reverse=True)
    return similar


def analyze_listening_patterns(
    streaming_history_df: pd.DataFrame,
    days: int = 30
) -> Dict[str, any]:
    """
    Analyze listening patterns over the last N days.
    
    Returns:
        Dictionary with insights:
        - top_artists: Most listened artists
        - top_tracks: Most played tracks
        - listening_hours: Total listening time
        - peak_hours: Hours of day with most listening
        - genre_distribution: Genre breakdown
        - discovery_rate: New tracks discovered
    """
    if streaming_history_df.empty:
        return {}
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Filter to recent data
    if "timestamp" in streaming_history_df.columns:
        recent = streaming_history_df[
            pd.to_datetime(streaming_history_df["timestamp"]) >= cutoff_date
        ].copy()
    else:
        recent = streaming_history_df.copy()
    
    if recent.empty:
        return {}
    
    insights = {}
    
    # Top artists
    if "artist_name" in recent.columns:
        insights["top_artists"] = recent["artist_name"].value_counts().head(10).to_dict()
    
    # Top tracks
    if "track_name" in recent.columns:
        insights["top_tracks"] = recent["track_name"].value_counts().head(10).to_dict()
    
    # Listening hours
    if "ms_played" in recent.columns:
        total_ms = recent["ms_played"].sum()
        insights["listening_hours"] = round(total_ms / (1000 * 60 * 60), 1)
    
    # Peak hours
    if "timestamp" in recent.columns:
        recent["hour"] = pd.to_datetime(recent["timestamp"]).dt.hour
        insights["peak_hours"] = recent["hour"].value_counts().head(5).to_dict()
    
    # Discovery rate (tracks played for first time)
    if "track_name" in recent.columns:
        first_plays = recent.drop_duplicates(subset=["track_name"], keep="first")
        insights["discovery_rate"] = len(first_plays) / len(recent) if len(recent) > 0 else 0
    
    return insights


def suggest_playlist_merge_candidates(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    similarity_threshold: float = 0.5,
    size_threshold: int = 20
) -> List[Dict[str, any]]:
    """
    Suggest playlists that could be merged based on similarity.
    
    Args:
        similarity_threshold: Minimum similarity to suggest merge
        size_threshold: Minimum playlist size to consider
    
    Returns:
        List of merge suggestions with details
    """
    suggestions = []
    
    # Get owned playlists only
    owned = (
        playlists_df[playlists_df["is_owned"] == True].copy()
        if "is_owned" in playlists_df.columns
        else playlists_df.copy()
    )
    
    # Build track sets
    playlist_tracks = {}
    for _, row in owned.iterrows():
        playlist_id = row["playlist_id"]
        tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
        track_set = set(tracks["track_id"].unique())
        if len(track_set) >= size_threshold:
            playlist_tracks[playlist_id] = {
                "name": row["name"],
                "tracks": track_set,
                "size": len(track_set)
            }
    
    # Find similar pairs
    playlist_ids = list(playlist_tracks.keys())
    for i, pid1 in enumerate(playlist_ids):
        for pid2 in playlist_ids[i+1:]:
            pl1 = playlist_tracks[pid1]
            pl2 = playlist_tracks[pid2]
            
            similarity = calculate_playlist_similarity(pl1["tracks"], pl2["tracks"])
            
            if similarity >= similarity_threshold:
                # Calculate merge benefits
                unique_tracks = len(pl1["tracks"] | pl2["tracks"])
                overlap = len(pl1["tracks"] & pl2["tracks"])
                
                suggestions.append({
                    "playlist1": pl1["name"],
                    "playlist2": pl2["name"],
                    "similarity": round(similarity, 2),
                    "overlap": overlap,
                    "unique_tracks": unique_tracks,
                    "size1": pl1["size"],
                    "size2": pl2["size"],
                    "merge_benefit": f"Would combine {pl1['size']} + {pl2['size']} = {unique_tracks} unique tracks"
                })
    
    # Sort by similarity
    suggestions.sort(key=lambda x: x["similarity"], reverse=True)
    return suggestions


def generate_listening_insights_report(
    playlists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    tracks_df: pd.DataFrame,
    streaming_history_df: Optional[pd.DataFrame] = None
) -> str:
    """
    Generate a creative, formatted insights report.
    
    Returns:
        Formatted report string
    """
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("🎵 SPOTIM8 LISTENING INSIGHTS REPORT")
    report_lines.append("=" * 70)
    report_lines.append("")
    
    # Library statistics
    total_playlists = (
        len(playlists_df[playlists_df["is_owned"] == True])
        if "is_owned" in playlists_df.columns
        else len(playlists_df)
    )
    total_tracks = len(playlist_tracks_df)
    unique_tracks = playlist_tracks_df["track_id"].nunique()
    
    report_lines.append("📊 LIBRARY OVERVIEW")
    report_lines.append("-" * 70)
    report_lines.append(f"   🎵 Total Playlists: {total_playlists:,}")
    report_lines.append(f"   🎶 Total Track Entries: {total_tracks:,}")
    report_lines.append(f"   🎧 Unique Tracks: {unique_tracks:,}")
    report_lines.append("")
    
    # Genre distribution
    if "genres" in tracks_df.columns:
        all_genres = []
        for genres_list in tracks_df["genres"].dropna():
            if isinstance(genres_list, list):
                all_genres.extend(genres_list)
        
        if all_genres:
            genre_counts = Counter(all_genres)
            top_genres = genre_counts.most_common(10)
            
            report_lines.append("🎸 TOP GENRES")
            report_lines.append("-" * 70)
            for genre, count in top_genres:
                percentage = (count / len(all_genres)) * 100
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length
                report_lines.append(f"   {genre:20s} {bar} {count:4d} ({percentage:5.1f}%)")
            report_lines.append("")
    
    # Listening patterns (if streaming history available)
    if streaming_history_df is not None and not streaming_history_df.empty:
        patterns = analyze_listening_patterns(streaming_history_df, days=30)
        
        if patterns:
            report_lines.append("📈 RECENT LISTENING PATTERNS (Last 30 Days)")
            report_lines.append("-" * 70)
            
            if "listening_hours" in patterns:
                report_lines.append(f"   ⏱️  Total Listening Time: {patterns['listening_hours']} hours")
            
            if "top_artists" in patterns:
                report_lines.append(f"   🎤 Top Artist: {list(patterns['top_artists'].keys())[0]}")
            
            if "discovery_rate" in patterns:
                rate = patterns["discovery_rate"] * 100
                report_lines.append(f"   🔍 Discovery Rate: {rate:.1f}% new tracks")
            
            if "peak_hours" in patterns:
                peak_hour = max(patterns["peak_hours"].items(), key=lambda x: x[1])[0]
                report_lines.append(f"   ⏰ Peak Listening Hour: {peak_hour}:00")
            
            report_lines.append("")
    
    # Playlist similarity insights
    similar = find_similar_playlists(playlists_df, playlist_tracks_df, threshold=0.3)
    if similar:
        report_lines.append("🔗 SIMILAR PLAYLISTS")
        report_lines.append("-" * 70)
        for name1, name2, sim in similar[:5]:  # Top 5
            sim_pct = sim * 100
            report_lines.append(f"   {name1[:30]:30s} ↔ {name2[:30]:30s} ({sim_pct:.0f}% similar)")
        report_lines.append("")
    
    # Merge suggestions
    merge_candidates = suggest_playlist_merge_candidates(
        playlists_df, playlist_tracks_df, similarity_threshold=0.5
    )
    if merge_candidates:
        report_lines.append("💡 MERGE SUGGESTIONS")
        report_lines.append("-" * 70)
        for suggestion in merge_candidates[:3]:  # Top 3
            report_lines.append(f"   • {suggestion['playlist1']} + {suggestion['playlist2']}")
            report_lines.append(f"     Similarity: {suggestion['similarity']*100:.0f}% | {suggestion['merge_benefit']}")
        report_lines.append("")
    
    report_lines.append("=" * 70)
    
    return "\n".join(report_lines)


def calculate_playlist_health_score(
    playlist_id: str,
    playlist_tracks_df: pd.DataFrame,
    tracks_df: pd.DataFrame
) -> Dict[str, any]:
    """
    Calculate a health score for a playlist.
    
    Factors:
    - Track count (more is better, but not too many)
    - Genre diversity
    - Metadata completeness
    - Duplicate tracks (penalty)
    
    Returns:
        Dictionary with score (0-100) and breakdown
    """
    tracks = playlist_tracks_df[playlist_tracks_df["playlist_id"] == playlist_id]
    
    if tracks.empty:
        return {"score": 0, "factors": {"empty": True}}
    
    factors = {}
    score = 100
    
    # Track count (optimal: 20-100 tracks)
    track_count = len(tracks)
    if track_count < 10:
        score -= 20
        factors["too_small"] = track_count
    elif track_count > 500:
        score -= 10
        factors["too_large"] = track_count
    else:
        factors["good_size"] = track_count
    
    # Duplicates (penalty)
    duplicates = tracks["track_id"].duplicated().sum()
    if duplicates > 0:
        score -= min(duplicates * 2, 20)
        factors["duplicates"] = duplicates
    
    # Genre diversity (bonus)
    merged = tracks.merge(tracks_df, on="track_id", how="left")
    if "genres" in merged.columns:
        all_genres = []
        for genres_list in merged["genres"].dropna():
            if isinstance(genres_list, list):
                all_genres.extend(genres_list)
        
        unique_genres = len(set(all_genres))
        if unique_genres >= 5:
            score += min(unique_genres - 5, 10)
            factors["genre_diversity"] = unique_genres
    
    # Metadata completeness
    if "popularity" in merged.columns:
        missing_pop = merged["popularity"].isna().sum()
        if missing_pop > len(merged) * 0.1:
            score -= 5
            factors["missing_metadata"] = missing_pop
    
    score = max(0, min(100, score))  # Clamp to 0-100
    
    return {
        "score": score,
        "factors": factors,
        "track_count": track_count
    }
