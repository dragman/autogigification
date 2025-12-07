import logging
from typing import Optional, Tuple

from ag.cache import create_cache, create_null_cache
from ag.clients.setlist_fm import SetlistFmClient
from ag.clients.spotify import SpotifyClient
from ag.config import load_app_config
from ag.services.playlist_builder import PlaylistBuilder
from ag.utils.rate_limit import NullRateLimiter, RateLimiter


def _build_builder(no_cache: bool, rate_limit: float) -> PlaylistBuilder:
    cfg = load_app_config()
    setlist_cache = (
        create_null_cache() if no_cache else create_cache(cfg.caches.setlist_cache)
    )
    spotify_cache = (
        create_null_cache()
        if no_cache
        else create_cache(cfg.caches.spotify_track_cache)
    )

    rate_limiter: Optional[RateLimiter] = (
        NullRateLimiter() if rate_limit <= 0 else RateLimiter(rate_limit)
    )

    setlist_client = SetlistFmClient(
        cfg.setlist_fm.api_key, cache=setlist_cache, rate_limiter=rate_limiter
    )
    spotify_client = SpotifyClient(cfg.spotify, track_cache=spotify_cache)

    return PlaylistBuilder(setlist_client, spotify_client)


def run_playlist_job(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    *,
    no_cache: bool = False,
    rate_limit: float = 1.0,
    use_fuzzy_search: bool = False,
):
    """Shared orchestration for CLI/Lambda to create a playlist."""
    if not band_names:
        raise ValueError("band_names cannot be empty")

    builder = _build_builder(no_cache, rate_limit)
    playlist = builder.build_playlist(
        band_names,
        playlist_name,
        copy_last_setlist_threshold,
        max_setlist_length,
        use_fuzzy_search=use_fuzzy_search,
    )

    logging.info("Playlist created: %s", playlist)
    return playlist
