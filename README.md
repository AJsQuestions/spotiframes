# spotifyframes

A minimal, elegant **pandas-first** interface to the Spotify Web API.

Turn your Spotify library into tidy DataFrames you can `merge()`, analyze, and visualize.

## Features

- 🎵 **Your Library**: Playlists, tracks, artists, liked songs
- 📊 **Pandas DataFrames**: Everything as tidy, mergeable tables
- 🔄 **Incremental Sync**: Only fetch what's changed
- 💾 **Local Cache**: Parquet files for fast offline access
- 🛡️ **Rate Limiting**: Built-in handling of Spotify API limits

## Install

```bash
pip install -e .

# With notebook dependencies:
pip install -e ".[notebook]"
```

## Setup

1. Create a Spotify app at [developer.spotify.com](https://developer.spotify.com/dashboard)
2. Add redirect URI: `http://127.0.0.1:8888/callback`
3. Set environment variables:

```bash
export SPOTIPY_CLIENT_ID="your_client_id"
export SPOTIPY_CLIENT_SECRET="your_client_secret"
export SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
```

## Quickstart

```python
from spotifyframes import SpotifyFrames

sf = SpotifyFrames.from_env(progress=True)

# Sync your library (incremental updates)
sf.sync(owned_only=True, include_liked_songs=True)

# Access your data
playlists = sf.playlists()      # All your playlists
tracks = sf.tracks()            # All unique tracks
artists = sf.artists()          # All artists with genres
wide = sf.library_wide()        # Everything joined together
```

## Available Data

| Table | Description |
|-------|-------------|
| `playlists()` | Your playlists (including ❤️ Liked Songs) |
| `playlist_tracks()` | Track-playlist relationships |
| `tracks()` | Track metadata (name, duration, popularity) |
| `track_artists()` | Track-artist relationships |
| `artists()` | Artist info with genres |
| `library_wide()` | Everything joined |

### Spotify API Changes (Nov 2024)

Spotify deprecated these endpoints for new apps:
- ❌ Audio features (danceability, energy, etc.)
- ❌ Audio analysis
- ⚠️ Recommendations (may work for older apps)

This library focuses on what's still available.

## CLI

```bash
# Sync your library
spotifyframes refresh

# Check status
spotifyframes status

# Export to file
spotifyframes export --table tracks --out data/tracks.parquet
spotifyframes export --table library_wide --out data/library.csv

# Market data
spotifyframes market --kind new_releases --country US --out releases.parquet
spotifyframes market --kind search_tracks --q "indie rock" --out search.parquet
```

## Market Layer

Access Spotify's browse and search APIs:

```python
# New releases
releases = sf.market.new_releases(country="US", limit=50)

# Categories
categories = sf.market.categories(country="US")

# Search
tracks = sf.market.search_tracks("indie rock", limit=100)
playlists = sf.market.search_playlists("workout", limit=50)
```

## Notebooks

The `notebooks/` folder contains analysis notebooks:

1. **`01_sync_data.ipynb`** - Download and cache your library
2. **`02_analyze_library.ipynb`** - Basic library analysis
3. **`03_playlist_analysis.ipynb`** - Genre analysis and playlist clustering

## Feature Engineering

```python
from spotifyframes import build_all_features

# Build features for ML/analysis
features = build_all_features(sf.library_wide())
```

Available features:
- Popularity statistics (mean, median, std)
- Duration statistics
- Artist concentration (HHI, entropy)
- Release year distribution
- Popularity tier breakdown

## Configuration

```python
from spotifyframes import SpotifyFrames, CacheConfig
from pathlib import Path

# Custom cache directory
config = CacheConfig(
    enabled=True,
    dir=Path("./my_data"),
    fmt="parquet",  # or "csv"
)

sf = SpotifyFrames.from_env(cache=config, progress=True)
```

## License

MIT
