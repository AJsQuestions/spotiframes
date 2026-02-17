"""
Common utilities for src scripts.

Shared functions and setup code used across all scripts.
"""


def __getattr__(name):
    """Lazy imports to avoid pulling in pandas/spotipy when only config_helpers is needed."""
    _path_names = {"get_project_root", "get_data_dir"}
    if name in _path_names:
        from .project_path import get_project_root, get_data_dir
        return globals()[name]

    if name == "setup_script_environment":
        from .setup import setup_script_environment
        return setup_script_environment

    _api_names = {"get_spotify_client", "get_user_info", "api_call", "chunked"}
    if name in _api_names:
        from .api_helpers import get_spotify_client, get_user_info, api_call, chunked
        return globals()[name]

    _playlist_names = {
        "find_playlist_by_name", "get_playlist_earliest_timestamp",
        "get_playlist_tracks", "to_uri", "uri_to_track_id", "add_tracks_to_playlist",
    }
    if name in _playlist_names:
        from .playlist_utils import (
            find_playlist_by_name, get_playlist_earliest_timestamp,
            get_playlist_tracks, to_uri, uri_to_track_id, add_tracks_to_playlist,
        )
        return globals()[name]

    if name == "trigger_incremental_sync":
        from .sync_helpers import trigger_incremental_sync
        return trigger_incremental_sync

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Path utilities
    "get_project_root",
    "get_data_dir",
    "setup_script_environment",
    # API helpers
    "get_spotify_client",
    "get_user_info",
    "api_call",
    "chunked",
    # Playlist utilities
    "find_playlist_by_name",
    "get_playlist_earliest_timestamp",
    "get_playlist_tracks",
    "to_uri",
    "uri_to_track_id",
    "add_tracks_to_playlist",
    # Sync helpers
    "trigger_incremental_sync",
]
