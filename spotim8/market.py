"""
Market data interface for Spotify browse, search, and recommendations.
"""

from __future__ import annotations

from typing import Optional, Callable

import pandas as pd

from .ratelimit import rate_limited_call, DEFAULT_REQUEST_DELAY


class MarketFrames:
    """Market / population-ish signals built from Spotify browse + search."""

    def __init__(self, sp, progress=None, request_delay: float = DEFAULT_REQUEST_DELAY):
        self.sp = sp
        self.progress = progress
        self._request_delay = request_delay
    
    def _rate_limited(self, func: Callable, *args, **kwargs):
        """Wrapper for rate-limited API calls."""
        return rate_limited_call(func, *args, delay=self._request_delay, **kwargs)

    # ------------------ Browse ------------------
    def new_releases(self, country: str = "US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.new_releases, country=country, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("albums") or {}).get("items", [])
            for a in items:
                out.append({
                    "album_id": a.get("id"),
                    "album_name": a.get("name"),
                    "release_date": a.get("release_date"),
                    "album_type": a.get("album_type"),
                    "total_tracks": a.get("total_tracks"),
                    "popularity": a.get("popularity"),
                    "label": a.get("label"),
                    "artists": [x.get("name") for x in a.get("artists", [])],
                    "artist_ids": [x.get("id") for x in a.get("artists", [])],
                    "uri": a.get("uri"),
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def categories(self, country: str = "US", locale: str = "en_US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.categories, country=country, locale=locale, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("categories") or {}).get("items", [])
            for c in items:
                out.append({
                    "category_id": c.get("id"),
                    "name": c.get("name"),
                    "href": c.get("href"),
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def category_playlists(self, category_id: str, country: str = "US", limit: int = 50) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.category_playlists, category_id, country=country, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("playlists") or {}).get("items", [])
            for p in items:
                owner = p.get("owner") or {}
                out.append({
                    "playlist_id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "snapshot_id": p.get("snapshot_id"),
                    "track_count": (p.get("tracks") or {}).get("total"),
                    "owner_id": owner.get("id"),
                    "owner_name": owner.get("display_name"),
                    "uri": p.get("uri"),
                    "category_id": category_id,
                    "country": country,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    # ------------------ Search ------------------
    def search_tracks(self, q: str, market: str = "US", limit: int = 200) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.search, q=q, type="track", market=market, limit=min(50, limit-offset), offset=offset)
            items = (resp.get("tracks") or {}).get("items", [])
            for t in items:
                album = t.get("album") or {}
                out.append({
                    "track_id": t.get("id"),
                    "track_name": t.get("name"),
                    "popularity": t.get("popularity"),
                    "duration_ms": t.get("duration_ms"),
                    "explicit": t.get("explicit"),
                    "album_id": album.get("id"),
                    "album_name": album.get("name"),
                    "release_date": album.get("release_date"),
                    "artist_ids": [a.get("id") for a in t.get("artists", [])],
                    "artists": [a.get("name") for a in t.get("artists", [])],
                    "uri": t.get("uri"),
                    "query": q,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

    def search_playlists(self, q: str, limit: int = 200) -> pd.DataFrame:
        out = []
        offset = 0
        while True:
            resp = self._rate_limited(self.sp.search, q=q, type="playlist", limit=min(50, limit-offset), offset=offset)
            items = (resp.get("playlists") or {}).get("items", [])
            for p in items:
                owner = p.get("owner") or {}
                out.append({
                    "playlist_id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "snapshot_id": p.get("snapshot_id"),
                    "track_count": (p.get("tracks") or {}).get("total"),
                    "owner_id": owner.get("id"),
                    "owner_name": owner.get("display_name"),
                    "uri": p.get("uri"),
                    "query": q,
                })
            offset += len(items)
            if offset >= limit or not items:
                break
        return pd.DataFrame(out)

