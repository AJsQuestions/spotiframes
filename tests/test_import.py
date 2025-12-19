"""Test that all public exports are importable."""

import pytest


def test_import_main():
    """Test importing main module."""
    import spotifyframes
    assert hasattr(spotifyframes, 'SpotifyFrames')
    assert hasattr(spotifyframes, '__version__')


def test_import_client():
    """Test importing from client."""
    from spotifyframes import SpotifyFrames, LIKED_SONGS_PLAYLIST_ID, LIKED_SONGS_PLAYLIST_NAME
    assert SpotifyFrames is not None
    assert LIKED_SONGS_PLAYLIST_ID == "__liked_songs__"


def test_import_catalog():
    """Test importing catalog classes."""
    from spotifyframes import CacheConfig, DataCatalog
    assert CacheConfig is not None
    assert DataCatalog is not None


def test_import_features():
    """Test importing feature functions."""
    from spotifyframes import (
        playlist_profile_features,
        artist_concentration_features,
        time_features,
        release_year_features,
        popularity_tier_features,
        build_all_features,
    )
    assert all([
        playlist_profile_features,
        artist_concentration_features,
        time_features,
        release_year_features,
        popularity_tier_features,
        build_all_features,
    ])


def test_import_ratelimit():
    """Test importing rate limiting utilities."""
    from spotifyframes.ratelimit import (
        rate_limited_call,
        RateLimiter,
        RateLimitError,
        DEFAULT_REQUEST_DELAY,
    )
    assert rate_limited_call is not None
    assert RateLimiter is not None
    assert RateLimitError is not None
    assert DEFAULT_REQUEST_DELAY > 0


def test_import_market():
    """Test importing market module."""
    from spotifyframes.market import MarketFrames
    assert MarketFrames is not None
