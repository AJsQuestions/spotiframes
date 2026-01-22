"""
Advanced Multi-Dimensional Genre Classification

Creative genre classification using:
1. Collaborative filtering (similar tracks)
2. Temporal patterns (when tracks were added/listened)
3. Artist network analysis (collaboration patterns)
4. Playlist co-occurrence (tracks that appear together)
5. Release year + genre evolution (temporal trends)
6. Hybrid scoring (weighted combination of signals)
7. Dynamic genre discovery (learns from user patterns)
8. Context-aware classification (playlist context)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import math

from .genres import (
    get_all_broad_genres, get_all_split_genres,
    GENRE_RULES, GENRE_SPLIT_RULES, ALL_BROAD_GENRES
)


class AdvancedGenreClassifier:
    """
    Multi-dimensional genre classifier using creative approaches.
    
    Uses multiple signals beyond just artist genres:
    - Collaborative filtering from similar tracks
    - Temporal patterns and listening history
    - Artist collaboration networks
    - Playlist co-occurrence patterns
    - Release year and genre evolution
    - Dynamic genre discovery from user patterns
    """
    
    def __init__(
        self,
        tracks_df: pd.DataFrame,
        track_artists_df: pd.DataFrame,
        artists_df: pd.DataFrame,
        playlist_tracks_df: pd.DataFrame,
        playlists_df: pd.DataFrame,
        streaming_history_df: Optional[pd.DataFrame] = None
    ):
        self.tracks_df = tracks_df
        self.track_artists_df = track_artists_df
        self.artists_df = artists_df
        self.playlist_tracks_df = playlist_tracks_df
        self.playlists_df = playlists_df
        self.streaming_history_df = streaming_history_df
        
        # Build caches for fast lookups
        self._build_caches()
        
        # Learn genre patterns from user's library
        self._learn_user_genre_patterns()
    
    def _build_caches(self):
        """Build fast lookup caches."""
        # Track -> Artists mapping
        self.track_artists_map = defaultdict(set)
        for _, row in self.track_artists_df.iterrows():
            self.track_artists_map[row["track_id"]].add(row["artist_id"])
        
        # Artist -> Genres mapping
        self.artist_genres_map = {}
        for _, row in self.artists_df.iterrows():
            genres = row.get("genres", [])
            if isinstance(genres, list):
                self.artist_genres_map[row["artist_id"]] = genres
            elif isinstance(genres, str):
                try:
                    import ast
                    self.artist_genres_map[row["artist_id"]] = ast.literal_eval(genres)
                except:
                    self.artist_genres_map[row["artist_id"]] = []
            else:
                self.artist_genres_map[row["artist_id"]] = []
        
        # Track -> Playlists mapping
        self.track_playlists_map = defaultdict(set)
        for _, row in self.playlist_tracks_df.iterrows():
            self.track_playlists_map[row["track_id"]].add(row["playlist_id"])
        
        # Playlist -> Tracks mapping
        self.playlist_tracks_map = defaultdict(set)
        for _, row in self.playlist_tracks_df.iterrows():
            self.playlist_tracks_map[row["playlist_id"]].add(row["track_id"])
        
        # Artist collaboration network (artists that appear together on tracks)
        self.artist_collaborations = defaultdict(set)
        for track_id, artist_ids in self.track_artists_map.items():
            artist_list = list(artist_ids)
            for i, artist1 in enumerate(artist_list):
                for artist2 in artist_list[i+1:]:
                    self.artist_collaborations[artist1].add(artist2)
                    self.artist_collaborations[artist2].add(artist1)
    
    def _learn_user_genre_patterns(self):
        """Learn genre patterns from user's library and playlists."""
        # Analyze playlist names/descriptions for genre keywords
        self.playlist_genre_signals = defaultdict(Counter)
        
        for _, pl_row in self.playlists_df.iterrows():
            pl_id = pl_row.get("playlist_id")
            pl_name = str(pl_row.get("name", "")).lower()
            pl_desc = str(pl_row.get("description", "")).lower()
            pl_text = f"{pl_name} {pl_desc}"
            
            # Get tracks in this playlist
            track_ids = self.playlist_tracks_map.get(pl_id, set())
            
            # Match genre keywords
            for keywords, category in GENRE_RULES:
                for keyword in keywords:
                    if keyword.lower() in pl_text:
                        # Signal strength based on playlist size
                        signal_strength = min(len(track_ids) / 10, 5)  # Cap at 5
                        for track_id in track_ids:
                            self.playlist_genre_signals[track_id][category] += signal_strength
        
        # Analyze release year patterns (genre evolution over time)
        self.year_genre_patterns = defaultdict(Counter)
        if "release_year" in self.tracks_df.columns:
            for _, track_row in self.tracks_df.iterrows():
                track_id = track_row["track_id"]
                year = track_row.get("release_year")
                if pd.notna(year) and isinstance(year, (int, float)):
                    year = int(year)
                    # Get genres for this track
                    genres = self._get_track_genres_from_artists(track_id)
                    broad_genres = get_all_broad_genres(genres)
                    for genre in broad_genres:
                        self.year_genre_patterns[year][genre] += 1
    
    def _get_track_genres_from_artists(self, track_id: str) -> List[str]:
        """Get all genres from all artists on a track."""
        artist_ids = self.track_artists_map.get(track_id, set())
        all_genres = []
        for artist_id in artist_ids:
            genres = self.artist_genres_map.get(artist_id, [])
            all_genres.extend(genres)
        return list(set(all_genres))  # Unique genres
    
    def classify_track(
        self,
        track_id: str,
        mode: str = "broad",  # "broad" or "split"
        use_collaborative: bool = True,
        use_temporal: bool = True,
        use_network: bool = True,
        use_cooccurrence: bool = True
    ) -> Dict[str, float]:
        """
        Classify a track using multiple signals.
        
        Returns:
            Dictionary mapping genre names to confidence scores (0.0-1.0)
        """
        scores = defaultdict(float)
        
        # Signal 1: Artist genres (base signal, always used)
        artist_genres = self._get_track_genres_from_artists(track_id)
        if mode == "broad":
            base_genres = get_all_broad_genres(artist_genres)
        else:
            base_genres = get_all_split_genres(artist_genres)
        
        for genre in base_genres:
            scores[genre] += 0.4  # Base weight
        
        # Signal 2: Collaborative filtering (similar tracks)
        if use_collaborative:
            similar_scores = self._collaborative_filtering(track_id, mode)
            for genre, score in similar_scores.items():
                scores[genre] += score * 0.25
        
        # Signal 3: Playlist co-occurrence
        if use_cooccurrence:
            cooccurrence_scores = self._playlist_cooccurrence(track_id, mode)
            for genre, score in cooccurrence_scores.items():
                scores[genre] += score * 0.15
        
        # Signal 4: Artist network (collaboration patterns)
        if use_network:
            network_scores = self._artist_network_analysis(track_id, mode)
            for genre, score in network_scores.items():
                scores[genre] += score * 0.1
        
        # Signal 5: Temporal patterns (release year, listening patterns)
        if use_temporal:
            temporal_scores = self._temporal_patterns(track_id, mode)
            for genre, score in temporal_scores.items():
                scores[genre] += score * 0.1
        
        # Normalize scores to 0-1 range
        max_score = max(scores.values()) if scores else 0
        if max_score > 0:
            scores = {g: s / max_score for g, s in scores.items()}
        
        return dict(scores)
    
    def _collaborative_filtering(
        self,
        track_id: str,
        mode: str
    ) -> Dict[str, float]:
        """
        Use collaborative filtering: tracks with similar artists/genres.
        
        Finds tracks that share artists or appear in same playlists,
        then uses their genres as signals.
        """
        scores = defaultdict(float)
        
        # Find similar tracks (share artists)
        track_artists = self.track_artists_map.get(track_id, set())
        similar_tracks = []
        
        for other_track_id, other_artists in self.track_artists_map.items():
            if other_track_id == track_id:
                continue
            
            # Similarity: shared artists
            shared = track_artists & other_artists
            if shared:
                similarity = len(shared) / max(len(track_artists), len(other_artists))
                if similarity > 0.3:  # Threshold
                    similar_tracks.append((other_track_id, similarity))
        
        # Also find tracks in same playlists
        track_playlists = self.track_playlists_map.get(track_id, set())
        for other_track_id in self.track_playlists_map:
            if other_track_id == track_id:
                continue
            
            other_playlists = self.track_playlists_map.get(other_track_id, set())
            shared_playlists = track_playlists & other_playlists
            if shared_playlists:
                similarity = len(shared_playlists) / max(len(track_playlists), len(other_playlists), 1)
                if similarity > 0.2:
                    similar_tracks.append((other_track_id, similarity))
        
        # Get genres from similar tracks, weighted by similarity
        for similar_track_id, similarity in similar_tracks[:20]:  # Top 20
            genres = self._get_track_genres_from_artists(similar_track_id)
            if mode == "broad":
                similar_genres = get_all_broad_genres(genres)
            else:
                similar_genres = get_all_split_genres(genres)
            
            for genre in similar_genres:
                scores[genre] += similarity * 0.1
        
        return scores
    
    def _playlist_cooccurrence(
        self,
        track_id: str,
        mode: str
    ) -> Dict[str, float]:
        """
        Analyze playlist co-occurrence: tracks that appear together frequently.
        
        If track A and track B appear in many playlists together,
        and track B has a genre, that's a signal for track A.
        """
        scores = defaultdict(float)
        
        track_playlists = self.track_playlists_map.get(track_id, set())
        if not track_playlists:
            return scores
        
        # Find tracks that co-occur in playlists
        cooccurring_tracks = defaultdict(int)
        for pl_id in track_playlists:
            other_tracks = self.playlist_tracks_map.get(pl_id, set())
            for other_track_id in other_tracks:
                if other_track_id != track_id:
                    cooccurring_tracks[other_track_id] += 1
        
        # Get genres from frequently co-occurring tracks
        for other_track_id, count in sorted(
            cooccurring_tracks.items(),
            key=lambda x: x[1],
            reverse=True
        )[:15]:  # Top 15
            genres = self._get_track_genres_from_artists(other_track_id)
            if mode == "broad":
                other_genres = get_all_broad_genres(genres)
            else:
                other_genres = get_all_split_genres(genres)
            
            # Weight by co-occurrence frequency
            weight = min(count / 5, 1.0)  # Normalize
            for genre in other_genres:
                scores[genre] += weight * 0.05
        
        return scores
    
    def _artist_network_analysis(
        self,
        track_id: str,
        mode: str
    ) -> Dict[str, float]:
        """
        Analyze artist collaboration network.
        
        If an artist frequently collaborates with artists of a certain genre,
        that's a signal for that genre.
        """
        scores = defaultdict(float)
        
        track_artists = self.track_artists_map.get(track_id, set())
        if not track_artists:
            return scores
        
        # For each artist on this track, look at their collaborators
        for artist_id in track_artists:
            collaborators = self.artist_collaborations.get(artist_id, set())
            
            # Get genres from collaborators
            collaborator_genres = Counter()
            for collab_id in list(collaborators)[:20]:  # Top 20 collaborators
                genres = self.artist_genres_map.get(collab_id, [])
                if mode == "broad":
                    broad_genres = get_all_broad_genres(genres)
                else:
                    broad_genres = get_all_split_genres(genres)
                
                for genre in broad_genres:
                    collaborator_genres[genre] += 1
            
            # Weight by frequency
            total = sum(collaborator_genres.values())
            if total > 0:
                for genre, count in collaborator_genres.items():
                    scores[genre] += (count / total) * 0.05
        
        return scores
    
    def _temporal_patterns(
        self,
        track_id: str,
        mode: str
    ) -> Dict[str, float]:
        """
        Use temporal patterns: release year, listening patterns.
        
        Genres evolve over time - use year-based patterns.
        """
        scores = defaultdict(float)
        
        # Get track release year
        track_row = self.tracks_df[self.tracks_df["track_id"] == track_id]
        if track_row.empty:
            return scores
        
        year = track_row.iloc[0].get("release_year")
        if pd.notna(year) and isinstance(year, (int, float)):
            year = int(year)
            
            # Use genre patterns from that year
            year_patterns = self.year_genre_patterns.get(year, Counter())
            if not year_patterns:
                # Use nearby years (±2 years)
                for nearby_year in range(year - 2, year + 3):
                    if nearby_year in self.year_genre_patterns:
                        year_patterns.update(self.year_genre_patterns[nearby_year])
            
            total = sum(year_patterns.values())
            if total > 0:
                for genre, count in year_patterns.items():
                    # Only use if matches mode
                    if mode == "broad":
                        if genre in ALL_BROAD_GENRES:
                            scores[genre] += (count / total) * 0.03
                    else:
                        # Convert broad to split if needed
                        # This is approximate - could be improved
                        pass
        
        # Use playlist genre signals (learned from playlist names)
        playlist_signals = self.playlist_genre_signals.get(track_id, Counter())
        if playlist_signals:
            total = sum(playlist_signals.values())
            if total > 0:
                for genre, signal in playlist_signals.items():
                    if mode == "broad":
                        if genre in ALL_BROAD_GENRES:
                            scores[genre] += (signal / total) * 0.05
        
        return scores
    
    def classify_tracks_batch(
        self,
        track_ids: List[str],
        mode: str = "broad",
        min_confidence: float = 0.3
    ) -> pd.DataFrame:
        """
        Classify multiple tracks at once.
        
        Returns:
            DataFrame with track_id, genre, confidence columns
        """
        results = []
        
        for track_id in track_ids:
            scores = self.classify_track(track_id, mode=mode)
            
            # Filter by minimum confidence
            for genre, confidence in scores.items():
                if confidence >= min_confidence:
                    results.append({
                        "track_id": track_id,
                        "genre": genre,
                        "confidence": confidence
                    })
        
        return pd.DataFrame(results)
    
    def get_top_genres(
        self,
        track_id: str,
        mode: str = "broad",
        top_n: int = 3,
        min_confidence: float = 0.2
    ) -> List[Tuple[str, float]]:
        """
        Get top N genres for a track with confidence scores.
        
        Returns:
            List of (genre, confidence) tuples, sorted by confidence
        """
        scores = self.classify_track(track_id, mode=mode)
        
        # Filter and sort
        filtered = [
            (genre, conf) for genre, conf in scores.items()
            if conf >= min_confidence
        ]
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return filtered[:top_n]


def enhance_genre_classification(
    tracks_df: pd.DataFrame,
    track_artists_df: pd.DataFrame,
    artists_df: pd.DataFrame,
    playlist_tracks_df: pd.DataFrame,
    playlists_df: pd.DataFrame,
    streaming_history_df: Optional[pd.DataFrame] = None,
    mode: str = "broad",
    min_confidence: float = 0.3
) -> pd.DataFrame:
    """
    Enhance genre classification for all tracks using advanced methods.
    
    Args:
        tracks_df: DataFrame with track_id and other track info
        track_artists_df: DataFrame with track_id and artist_id
        artists_df: DataFrame with artist_id and genres
        playlist_tracks_df: DataFrame with playlist_id and track_id
        playlists_df: DataFrame with playlist_id, name, description
        streaming_history_df: Optional streaming history
        mode: "broad" or "split"
        min_confidence: Minimum confidence threshold
    
    Returns:
        DataFrame with track_id, genre, confidence columns
    """
    classifier = AdvancedGenreClassifier(
        tracks_df=tracks_df,
        track_artists_df=track_artists_df,
        artists_df=artists_df,
        playlist_tracks_df=playlist_tracks_df,
        playlists_df=playlists_df,
        streaming_history_df=streaming_history_df
    )
    
    track_ids = tracks_df["track_id"].tolist()
    return classifier.classify_tracks_batch(
        track_ids,
        mode=mode,
        min_confidence=min_confidence
    )
