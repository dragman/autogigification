import logging
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

from ag.cache import create_cache, create_null_cache
from ag.clients.setlist_fm import SetlistFmClient
from ag.clients.spotify import SpotifyClient
from ag.config import load_app_config
from ag.models import PlaylistBuildResult
from ag.services.playlist_builder import PlaylistBuilder
from ag.utils.rate_limit import NullRateLimiter, RateLimiter


def _build_builder(
    no_cache: bool, rate_limit: float, *, require_spotify_user: bool = True
) -> PlaylistBuilder:
    cfg = load_app_config(require_spotify_user=require_spotify_user)
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
    create_playlist: bool = True,
    force_smart_setlist: Optional[bool] = None,
) -> PlaylistBuildResult:
    """Shared orchestration for CLI/Lambda to create or preview a playlist."""
    if not band_names:
        raise ValueError("band_names cannot be empty")

    builder = _build_builder(
        no_cache,
        rate_limit,
        require_spotify_user=create_playlist,
    )

    result = builder.build_playlist(
        band_names,
        playlist_name,
        copy_last_setlist_threshold,
        max_setlist_length,
        force_smart_setlist=force_smart_setlist,
        use_fuzzy_search=use_fuzzy_search,
        create_playlist=create_playlist,
    )

    logging.info("Playlist build complete (created=%s)", result.created_playlist)
    return result


def playlist_result_to_payload(result: PlaylistBuildResult) -> Dict[str, Any]:
    """Convert PlaylistBuildResult into a JSON-serializable structure."""
    return {
        "playlist": asdict(result.playlist) if result.playlist else None,
        "created_playlist": result.created_playlist,
        "setlists": [
            {
                "band": setlist.band,
                "setlist_type": setlist.setlist_type,
                "setlist_date": setlist.setlist_date,
                "last_setlist_age_days": setlist.last_setlist_age_days,
                "songs": [asdict(song) for song in setlist.songs],
                "missing_songs": setlist.missing_songs,
            }
            for setlist in result.setlists
        ],
    }
