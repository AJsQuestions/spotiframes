"""
Spotim8 - Pandas-first interface to Spotify Web API.

Turns Spotify into tidy DataFrames you can merge().

Usage:
    from src import Spotim8

    sf = Spotim8.from_env(progress=True)
    sf.sync()

    playlists = sf.playlists()
    tracks = sf.tracks()
    artists = sf.artists()
"""

__version__ = "6.0.0"


def __getattr__(name):
    """Lazy imports: heavy modules (pandas, numpy, spotipy) are only loaded on first access."""
    # Core client
    _client_names = ("Spotim8", "LIKED_SONGS_PLAYLIST_ID", "LIKED_SONGS_PLAYLIST_NAME", "DEFAULT_SCOPE")
    if name in _client_names:
        from .core.client import Spotim8, LIKED_SONGS_PLAYLIST_ID, LIKED_SONGS_PLAYLIST_NAME, DEFAULT_SCOPE
        _imports = locals()
        for _n in _client_names:
            globals()[_n] = _imports[_n]
        return globals()[name]

    # Core catalog
    _catalog_names = ("CacheConfig", "DataCatalog")
    if name in _catalog_names:
        from .core.catalog import CacheConfig, DataCatalog
        _imports = locals()
        for _n in _catalog_names:
            globals()[_n] = _imports[_n]
        return globals()[name]

    # Utils
    if name == "set_response_cache":
        from .utils.ratelimit import set_response_cache
        globals()["set_response_cache"] = set_response_cache
        return set_response_cache

    # Data export
    if name == "export_table":
        from .data.export import export_table
        globals()["export_table"] = export_table
        return export_table

    # Feature engineering
    _feature_names = (
        "playlist_profile_features", "artist_concentration_features",
        "time_features", "release_year_features",
        "popularity_tier_features", "build_all_features",
    )
    if name in _feature_names:
        from .features.features import (
            playlist_profile_features, artist_concentration_features,
            time_features, release_year_features,
            popularity_tier_features, build_all_features,
        )
        _imports = locals()
        for _n in _feature_names:
            globals()[_n] = _imports[_n]
        return globals()[name]

    # Analysis utilities
    _analysis_names = (
        "LibraryAnalyzer", "PlaylistSimilarityEngine",
        "get_genres_list", "build_playlist_genre_profiles",
        "canonical_core_genre",
    )
    if name in _analysis_names:
        from .analysis.analysis import (
            LibraryAnalyzer, PlaylistSimilarityEngine,
            get_genres_list, build_playlist_genre_profiles,
            canonical_core_genre,
        )
        _imports = locals()
        for _n in _analysis_names:
            globals()[_n] = _imports[_n]
        return globals()[name]

    # Streaming history
    _history_names = (
        "sync_all_export_data", "sync_streaming_history",
        "load_streaming_history", "load_search_queries_cached",
        "load_wrapped_data_cached", "load_follow_data_cached",
        "load_library_snapshot_cached", "load_playback_errors_cached",
        "load_playback_retries_cached", "load_webapi_events_cached",
    )
    if name in _history_names:
        from .analysis.streaming_history import (
            sync_all_export_data, sync_streaming_history,
            load_streaming_history, load_search_queries_cached,
            load_wrapped_data_cached, load_follow_data_cached,
            load_library_snapshot_cached, load_playback_errors_cached,
            load_playback_retries_cached, load_webapi_events_cached,
        )
        _imports = locals()
        for _n in _history_names:
            globals()[_n] = _imports[_n]
        return globals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main client
    "Spotim8",
    # Constants
    "LIKED_SONGS_PLAYLIST_ID",
    "LIKED_SONGS_PLAYLIST_NAME",
    "DEFAULT_SCOPE",
    # Configuration
    "CacheConfig",
    "DataCatalog",
    "set_response_cache",
    # Utilities
    "export_table",
    # Feature engineering
    "playlist_profile_features",
    "artist_concentration_features",
    "time_features",
    "release_year_features",
    "popularity_tier_features",
    "build_all_features",
    # Analysis utilities
    "LibraryAnalyzer",
    "PlaylistSimilarityEngine",
    "get_genres_list",
    "build_playlist_genre_profiles",
    "canonical_core_genre",
    # Streaming history and export data
    "sync_all_export_data",
    "sync_streaming_history",
    "load_streaming_history",
    "load_search_queries_cached",
    "load_wrapped_data_cached",
    "load_follow_data_cached",
    "load_library_snapshot_cached",
    "load_playback_errors_cached",
    "load_playback_retries_cached",
    "load_webapi_events_cached",
]
