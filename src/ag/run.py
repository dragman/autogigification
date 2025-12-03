import logging
from typing import Optional, Tuple

from ag.cache import create_cache, create_null_cache
from ag.impl import create_playlist_from_lineup
from ag.setlist import SETLIST_CACHE, SPOTIFY_TRACK_CACHE
from ag.utils.rate_limit import NullRateLimiter, RateLimiter


def run_playlist_job(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    *,
    no_cache: bool = False,
    rate_limit: float = 1.0,
):
    """Shared orchestration for CLI/Lambda to create a playlist."""
    if not band_names:
        raise ValueError("band_names cannot be empty")

    if no_cache:
        setlist_cache = create_null_cache()
        spotify_cache = create_null_cache()
    else:
        setlist_cache = create_cache(SETLIST_CACHE)
        spotify_cache = create_cache(SPOTIFY_TRACK_CACHE)

    rate_limiter: Optional[RateLimiter] = (
        NullRateLimiter() if rate_limit <= 0 else RateLimiter(rate_limit)
    )

    playlist = create_playlist_from_lineup(
        band_names,
        playlist_name,
        copy_last_setlist_threshold,
        max_setlist_length,
        setlist_cache=setlist_cache,
        spotify_cache=spotify_cache,
        rate_limiter=rate_limiter,
    )

    logging.info("Playlist created: %s", playlist)
    return playlist
