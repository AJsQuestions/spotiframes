"""
Dynamic Genre Discovery

Discovers new genre patterns from user's library:
- Identifies genre clusters in user's music
- Finds emerging genres and trends
- Detects genre hybrids and fusions
- Learns user-specific genre preferences
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple
from collections import Counter, defaultdict
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
import warnings

from .genres import get_all_broad_genres, ALL_BROAD_GENRES


def discover_genre_clusters(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    playlists_df: pd.DataFrame,
    n_clusters: int = 10
) -> Dict[int, Dict]:
    """
    Discover genre clusters in user's library using K-means clustering.
    
    Uses multiple features:
    - Artist genres (TF-IDF)
    - Playlist co-occurrence
    - Release year
    - Popularity
    
    Returns:
        Dictionary mapping cluster_id to cluster info (genres, tracks, etc.)
    """
    try:
        # Build feature matrix
        features = []
        track_ids = []
        
        # Feature 1: Artist genres (TF-IDF)
        artist_genres_text = []
        for _, track_row in tracks_df.iterrows():
            track_id = track_row["track_id"]
            track_ids.append(track_id)
            
            # Get all genres from all artists
            track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
            all_genres = []
            for _, ta_row in track_artists.iterrows():
                artist_id = ta_row["artist_id"]
                artist_row = artists_df[artists_df["artist_id"] == artist_id]
                if not artist_row.empty:
                    genres = artist_row.iloc[0].get("genres", [])
                    if isinstance(genres, list):
                        all_genres.extend(genres)
            
            artist_genres_text.append(" ".join(all_genres).lower())
        
        # Vectorize genres
        vectorizer = TfidfVectorizer(max_features=50, stop_words='english')
        try:
            genre_vectors = vectorizer.fit_transform(artist_genres_text)
            genre_features = genre_vectors.toarray()
        except:
            # Fallback if no genres
            genre_features = np.zeros((len(track_ids), 10))
        
        # Feature 2: Release year (normalized)
        years = []
        for _, track_row in tracks_df.iterrows():
            year = track_row.get("release_year", 2000)
            if pd.notna(year):
                years.append((int(year) - 2000) / 50)  # Normalize to 0-1
            else:
                years.append(0.5)
        year_features = np.array(years).reshape(-1, 1)
        
        # Feature 3: Popularity (normalized)
        popularities = []
        for _, track_row in tracks_df.iterrows():
            pop = track_row.get("popularity", 50)
            if pd.notna(pop):
                popularities.append(pop / 100)  # Normalize to 0-1
            else:
                popularities.append(0.5)
        pop_features = np.array(popularities).reshape(-1, 1)
        
        # Combine features
        if genre_features.shape[1] > 0:
            combined = np.hstack([genre_features, year_features, pop_features])
        else:
            combined = np.hstack([year_features, pop_features])
        
        # Cluster
        n_clusters = min(n_clusters, len(track_ids))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(combined)
        
        # Analyze clusters
        cluster_info = {}
        for cluster_id in range(n_clusters):
            cluster_tracks = [track_ids[i] for i in range(len(track_ids)) if clusters[i] == cluster_id]
            
            # Get genres for tracks in this cluster
            cluster_genres = Counter()
            for track_id in cluster_tracks:
                track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
                for _, ta_row in track_artists.iterrows():
                    artist_id = ta_row["artist_id"]
                    artist_row = artists_df[artists_df["artist_id"] == artist_id]
                    if not artist_row.empty:
                        genres = artist_row.iloc[0].get("genres", [])
                        if isinstance(genres, list):
                            for genre in genres:
                                cluster_genres[genre] += 1
            
            # Get broad genres
            all_genres_list = list(cluster_genres.keys())
            broad_genres = get_all_broad_genres(all_genres_list)
            
            cluster_info[cluster_id] = {
                "track_count": len(cluster_tracks),
                "top_genres": dict(cluster_genres.most_common(10)),
                "broad_genres": list(set(broad_genres)),
                "track_ids": cluster_tracks[:20]  # Sample
            }
        
        return cluster_info
    
    except Exception as e:
        warnings.warn(f"Genre clustering failed: {e}")
        return {}


def discover_genre_hybrids(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame
) -> List[Dict]:
    """
    Discover genre hybrids - tracks that blend multiple genres.
    
    Returns:
        List of hybrid genre combinations with example tracks
    """
    hybrids = defaultdict(list)
    
    for _, track_row in tracks_df.iterrows():
        track_id = track_row["track_id"]
        track_name = track_row.get("name", "Unknown")
        
        # Get all genres from all artists
        track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
        all_genres = []
        for _, ta_row in track_artists.iterrows():
            artist_id = ta_row["artist_id"]
            artist_row = artists_df[artists_df["artist_id"] == artist_id]
            if not artist_row.empty:
                genres = artist_row.iloc[0].get("genres", [])
                if isinstance(genres, list):
                    all_genres.extend(genres)
        
        # Get broad genres
        broad_genres = get_all_broad_genres(all_genres)
        
        # If track has 2+ broad genres, it's a hybrid
        if len(broad_genres) >= 2:
            hybrid_key = "+".join(sorted(broad_genres))
            hybrids[hybrid_key].append({
                "track_id": track_id,
                "track_name": track_name,
                "genres": broad_genres
            })
    
    # Return top hybrids (most common combinations)
    results = []
    for hybrid_key, tracks in sorted(hybrids.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        results.append({
            "hybrid": hybrid_key,
            "genres": hybrid_key.split("+"),
            "track_count": len(tracks),
            "example_tracks": tracks[:5]  # Top 5 examples
        })
    
    return results


def discover_emerging_genres(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    min_year: int = 2020
) -> List[Dict]:
    """
    Discover emerging genres - genres that are becoming more popular recently.
    
    Args:
        min_year: Minimum year to consider "recent"
    
    Returns:
        List of emerging genres with trend data
    """
    if "release_year" not in tracks_df.columns:
        return []
    
    # Analyze genre trends by year
    year_genre_counts = defaultdict(Counter)
    
    for _, track_row in tracks_df.iterrows():
        year = track_row.get("release_year")
        if pd.notna(year) and isinstance(year, (int, float)):
            year = int(year)
            if year >= min_year:
                track_id = track_row["track_id"]
                
                # Get genres
                track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
                all_genres = []
                for _, ta_row in track_artists.iterrows():
                    artist_id = ta_row["artist_id"]
                    artist_row = artists_df[artists_df["artist_id"] == artist_id]
                    if not artist_row.empty:
                        genres = artist_row.iloc[0].get("genres", [])
                        if isinstance(genres, list):
                            all_genres.extend(genres)
                
                broad_genres = get_all_broad_genres(all_genres)
                for genre in broad_genres:
                    year_genre_counts[year][genre] += 1
    
    # Calculate growth rates
    emerging = []
    for genre in ALL_BROAD_GENRES:
        recent_counts = []
        older_counts = []
        
        for year in sorted(year_genre_counts.keys()):
            count = year_genre_counts[year].get(genre, 0)
            if year >= min_year:
                recent_counts.append(count)
            else:
                older_counts.append(count)
        
        if recent_counts and older_counts:
            recent_avg = np.mean(recent_counts) if recent_counts else 0
            older_avg = np.mean(older_counts) if older_counts else 0
            
            if older_avg > 0:
                growth_rate = (recent_avg - older_avg) / older_avg
                if growth_rate > 0.2:  # 20% growth
                    emerging.append({
                        "genre": genre,
                        "growth_rate": growth_rate,
                        "recent_avg": recent_avg,
                        "older_avg": older_avg,
                        "recent_years": dict(year_genre_counts[y].get(genre, 0) for y in sorted(year_genre_counts.keys()) if y >= min_year)
                    })
    
    # Sort by growth rate
    emerging.sort(key=lambda x: x["growth_rate"], reverse=True)
    return emerging[:10]  # Top 10


def discover_user_genre_preferences(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    playlists_df: pd.DataFrame,
    streaming_history_df: Optional[pd.DataFrame] = None
) -> Dict:
    """
    Discover user's genre preferences based on listening patterns.
    
    Returns:
        Dictionary with preference insights
    """
    preferences = {
        "favorite_genres": [],
        "diverse_genres": [],
        "genre_concentration": {},
        "genre_evolution": {}
    }
    
    # Analyze all tracks
    all_genres = Counter()
    for _, track_row in tracks_df.iterrows():
        track_id = track_row["track_id"]
        
        track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
        track_genres = []
        for _, ta_row in track_artists.iterrows():
            artist_id = ta_row["artist_id"]
            artist_row = artists_df[artists_df["artist_id"] == artist_id]
            if not artist_row.empty:
                genres = artist_row.iloc[0].get("genres", [])
                if isinstance(genres, list):
                    track_genres.extend(genres)
        
        broad_genres = get_all_broad_genres(track_genres)
        for genre in broad_genres:
            all_genres[genre] += 1
    
    # Favorite genres (most common)
    preferences["favorite_genres"] = [
        {"genre": genre, "count": count}
        for genre, count in all_genres.most_common(10)
    ]
    
    # Genre concentration (how focused user's library is)
    total = sum(all_genres.values())
    if total > 0:
        top_genre_pct = (all_genres.most_common(1)[0][1] / total) * 100
        preferences["genre_concentration"] = {
            "top_genre_percentage": top_genre_pct,
            "is_focused": top_genre_pct > 40,  # More than 40% in one genre
            "genre_diversity_score": len(all_genres) / len(ALL_BROAD_GENRES)  # 0-1 scale
        }
    
    # Genre evolution over time (if release year available)
    if "release_year" in tracks_df.columns:
        year_genres = defaultdict(Counter)
        for _, track_row in tracks_df.iterrows():
            year = track_row.get("release_year")
            if pd.notna(year):
                year = int(year)
                track_id = track_row["track_id"]
                
                track_artists = track_artists_df[track_artists_df["track_id"] == track_id]
                track_genres = []
                for _, ta_row in track_artists.iterrows():
                    artist_id = ta_row["artist_id"]
                    artist_row = artists_df[artists_df["artist_id"] == artist_id]
                    if not artist_row.empty:
                        genres = artist_row.iloc[0].get("genres", [])
                        if isinstance(genres, list):
                            track_genres.extend(genres)
                
                broad_genres = get_all_broad_genres(track_genres)
                for genre in broad_genres:
                    year_genres[year][genre] += 1
        
        # Find trends
        preferences["genre_evolution"] = {
            "years_analyzed": sorted(year_genres.keys()),
            "trends": {}
        }
        
        for genre in ALL_BROAD_GENRES:
            counts = [year_genres[y].get(genre, 0) for y in sorted(year_genres.keys())]
            if counts and max(counts) > 0:
                # Simple trend: increasing, decreasing, or stable
                if len(counts) >= 2:
                    recent = np.mean(counts[-3:]) if len(counts) >= 3 else counts[-1]
                    older = np.mean(counts[:3]) if len(counts) >= 3 else counts[0]
                    if older > 0:
                        trend = "increasing" if recent > older * 1.2 else ("decreasing" if recent < older * 0.8 else "stable")
                        preferences["genre_evolution"]["trends"][genre] = {
                            "trend": trend,
                            "recent_avg": recent,
                            "older_avg": older
                        }
    
    return preferences
