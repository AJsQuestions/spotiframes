"""
Genre Classification Enhancement

Integrates advanced genre classification into the sync workflow.
Optionally enhances genre classification using multi-dimensional signals.
"""

import pandas as pd
from typing import Optional
from pathlib import Path

from src.features.genre_classification_advanced import AdvancedGenreClassifier
from src.features.genre_discovery import (
    discover_genre_clusters,
    discover_genre_hybrids,
    discover_emerging_genres,
    discover_user_genre_preferences
)


def enhance_track_genres(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    playlists_df: pd.DataFrame,
    streaming_history_df: Optional[pd.DataFrame] = None,
    mode: str = "broad",
    min_confidence: float = 0.3,
    save_enhanced: bool = True,
    data_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Enhance track genres using advanced classification.
    
    Args:
        tracks_df: Tracks DataFrame
        track_artists_df: Track-artist relationships
        artists_df: Artists DataFrame
        playlist_tracks_df: Playlist-track relationships
        playlists_df: Playlists DataFrame
        streaming_history_df: Optional streaming history
        mode: "broad" or "split"
        min_confidence: Minimum confidence threshold
        save_enhanced: Whether to save enhanced genres back to tracks_df
        data_dir: Data directory for saving
    
    Returns:
        Enhanced tracks DataFrame with additional genre columns
    """
    from .sync import log, verbose_log
    
    log("\n--- Enhancing Genre Classification ---")
    verbose_log("  Using multi-dimensional classification signals...")
    
    # Create classifier
    classifier = AdvancedGenreClassifier(
        tracks_df=tracks_df,
        track_artists_df=track_artists_df,
        artists_df=artists_df,
        playlist_tracks_df=playlist_tracks_df,
        playlists_df=playlists_df,
        streaming_history_df=streaming_history_df
    )
    
    # Classify tracks
    enhanced_genres = []
    track_ids = tracks_df["track_id"].tolist()
    
    verbose_log(f"  Classifying {len(track_ids)} tracks...")
    for i, track_id in enumerate(track_ids):
        if (i + 1) % 100 == 0:
            verbose_log(f"    Processed {i + 1}/{len(track_ids)} tracks...")
        
        scores = classifier.classify_track(track_id, mode=mode)
        
        # Get top genres above threshold
        top_genres = [
            genre for genre, conf in sorted(scores.items(), key=lambda x: x[1], reverse=True)
            if conf >= min_confidence
        ]
        
        enhanced_genres.append({
            "track_id": track_id,
            "enhanced_genres": top_genres,
            "genre_confidence": dict(scores)
        })
    
    # Merge back into tracks_df
    enhanced_df = pd.DataFrame(enhanced_genres)
    tracks_enhanced = tracks_df.merge(enhanced_df, on="track_id", how="left")
    
    # Save if requested
    if save_enhanced and data_dir:
        output_path = data_dir / "tracks_enhanced.parquet"
        tracks_enhanced.to_parquet(output_path, index=False)
        verbose_log(f"  Saved enhanced genres to {output_path}")
    
    log(f"  ✅ Enhanced genres for {len(enhanced_genres)} tracks")
    
    return tracks_enhanced


def generate_genre_discovery_report(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    playlists_df: pd.DataFrame,
    streaming_history_df: Optional[pd.DataFrame] = None,
    output_path: Optional[Path] = None
) -> str:
    """
    Generate a creative genre discovery report.
    
    Returns:
        Formatted report string
    """
    from .sync import log
    
    log("\n--- Genre Discovery Report ---")
    
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("🎵 GENRE DISCOVERY REPORT")
    report_lines.append("=" * 70)
    report_lines.append("")
    
    # Discover genre clusters
    try:
        clusters = discover_genre_clusters(
            tracks_df, track_artists_df, artists_df,
            playlist_tracks_df, playlists_df, n_clusters=10
        )
        
        if clusters:
            report_lines.append("🎯 GENRE CLUSTERS")
            report_lines.append("-" * 70)
            for cluster_id, info in list(clusters.items())[:5]:
                report_lines.append(f"  Cluster {cluster_id}: {info['track_count']} tracks")
                if info['broad_genres']:
                    report_lines.append(f"    Genres: {', '.join(info['broad_genres'][:3])}")
                report_lines.append("")
    except Exception as e:
        report_lines.append(f"  ⚠️  Clustering failed: {e}")
        report_lines.append("")
    
    # Discover genre hybrids
    try:
        hybrids = discover_genre_hybrids(tracks_df, track_artists_df, artists_df)
        
        if hybrids:
            report_lines.append("🔀 GENRE HYBRIDS")
            report_lines.append("-" * 70)
            for hybrid in hybrids[:5]:
                genres_str = " + ".join(hybrid['genres'])
                report_lines.append(f"  {genres_str}: {hybrid['track_count']} tracks")
                if hybrid['example_tracks']:
                    example = hybrid['example_tracks'][0]
                    report_lines.append(f"    Example: {example.get('track_name', 'Unknown')}")
                report_lines.append("")
    except Exception as e:
        report_lines.append(f"  ⚠️  Hybrid discovery failed: {e}")
        report_lines.append("")
    
    # Discover emerging genres
    try:
        emerging = discover_emerging_genres(tracks_df, track_artists_df, artists_df, min_year=2020)
        
        if emerging:
            report_lines.append("📈 EMERGING GENRES")
            report_lines.append("-" * 70)
            for genre_info in emerging[:5]:
                growth_pct = genre_info['growth_rate'] * 100
                report_lines.append(f"  {genre_info['genre']}: +{growth_pct:.0f}% growth")
                report_lines.append(f"    Recent avg: {genre_info['recent_avg']:.1f} tracks/year")
                report_lines.append("")
    except Exception as e:
        report_lines.append(f"  ⚠️  Emerging genre discovery failed: {e}")
        report_lines.append("")
    
    # User preferences
    try:
        preferences = discover_user_genre_preferences(
            tracks_df, track_artists_df, artists_df,
            playlist_tracks_df, playlists_df, streaming_history_df
        )
        
        if preferences.get("favorite_genres"):
            report_lines.append("❤️  YOUR GENRE PREFERENCES")
            report_lines.append("-" * 70)
            for genre_info in preferences["favorite_genres"][:5]:
                report_lines.append(f"  {genre_info['genre']}: {genre_info['count']} tracks")
            
            if preferences.get("genre_concentration"):
                conc = preferences["genre_concentration"]
                report_lines.append("")
                report_lines.append(f"  Focus: {'Focused' if conc['is_focused'] else 'Diverse'} library")
                report_lines.append(f"  Top genre: {conc['top_genre_percentage']:.1f}% of library")
                report_lines.append(f"  Diversity score: {conc['genre_diversity_score']:.2f}")
            report_lines.append("")
    except Exception as e:
        report_lines.append(f"  ⚠️  Preference analysis failed: {e}")
        report_lines.append("")
    
    report_lines.append("=" * 70)
    
    report = "\n".join(report_lines)
    
    # Save if path provided
    if output_path:
        output_path.write_text(report, encoding='utf-8')
        log(f"  💾 Report saved to: {output_path}")
    
    return report
