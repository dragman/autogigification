import logging
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import spotipy

from ag.cache import Cache, create_null_cache
from ag.hellfest import get_hellfest_lineup
from ag.setlist import (
    Playlist,
    extract_common_songs,
    extract_last_setlist,
    extract_smart_setlist,
    find_or_create_spotify_playlist,
    get_recent_setlists,
    make_spotify,
    populate_spotify_playlist,
)
from ag.utils.rate_limit import NullRateLimiter, RateLimiter

# Allows swapping/adding festival lineup sources for tests or future festivals.
FestivalResolver = Callable[[], Optional[List[str]]]
DEFAULT_FESTIVAL_RESOLVERS: Dict[str, FestivalResolver] = {
    "hellfest": get_hellfest_lineup
}


def resolve_lineup(
    band_names: Iterable[str], festival_resolvers: Dict[str, FestivalResolver]
) -> List[str]:
    lineup: List[str] = []
    for name in band_names:
        resolver = festival_resolvers.get(name.lower())
        if resolver:
            festival_lineup = resolver()
            if not festival_lineup:
                raise RuntimeError(f"Failed to get lineup for festival: {name}")
            lineup.extend(festival_lineup)
        else:
            lineup.append(name)
    return lineup


def collect_band_songs(
    band: str,
    *,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    setlist_cache: Cache,
    rate_limiter: Optional[RateLimiter] = None,
    force_smart_setlist: Optional[bool] = None,
) -> Optional[List[str]]:
    rate_limiter = rate_limiter or NullRateLimiter()
    setlists = get_recent_setlists(setlist_cache, band, rate_limiter=rate_limiter)
    if not setlists:
        logging.warning("No setlists found for %s", band)
        return None

    songs_by_date = extract_common_songs(setlists)

    songs, last_date = extract_last_setlist(songs_by_date)
    last_setlist_age = (pd.Timestamp.now() - last_date).days

    use_smart = (
        force_smart_setlist
        if force_smart_setlist is not None
        else should_use_smart_setlist(last_setlist_age, copy_last_setlist_threshold)
    )

    if use_smart:
        logging.info(
            "%s: Last setlist %s is %s days old. Smart setlist will be used.",
            band,
            last_date,
            last_setlist_age,
        )
        songs = extract_smart_setlist(songs_by_date, max_setlist_length)
    else:
        logging.info(
            "%s: Last setlist %s is fresh. Using last setlist.",
            band,
            last_date,
        )

    logging.info("%s: %s songs", band, len(songs))
    return songs


def should_use_smart_setlist(last_setlist_age_days: int, threshold_days: int) -> bool:
    """Decide whether to switch to smart setlist selection based on staleness."""
    return last_setlist_age_days > threshold_days


def create_and_populate_playlist(
    all_songs: Dict[str, List[str]],
    playlist_name: str,
    spotify_cache: Cache,
    sp: Optional[spotipy.Spotify] = None,
) -> Playlist:
    """
    Create (or find) a Spotify playlist and populate it with provided songs.

    Accepts an optional Spotify client for easier testing.
    """
    sp = sp or make_spotify()
    playlist = find_or_create_spotify_playlist(sp, playlist_name)
    populate_spotify_playlist(sp, playlist, all_songs, track_cache=spotify_cache)
    return playlist


def create_playlist_from_lineup(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    *,
    setlist_cache: Optional[Cache] = None,
    spotify_cache: Optional[Cache] = None,
    festival_resolvers: Optional[Dict[str, FestivalResolver]] = None,
    rate_limiter: Optional[RateLimiter] = None,
    force_smart_setlist: Optional[bool] = None,
) -> Playlist:
    """Create a Spotify playlist based on the Hellfest lineup."""

    setlist_cache = setlist_cache or create_null_cache()
    spotify_cache = spotify_cache or create_null_cache()
    festival_resolvers = festival_resolvers or DEFAULT_FESTIVAL_RESOLVERS
    rate_limiter = rate_limiter or RateLimiter(min_interval_seconds=1.0)

    lineup = resolve_lineup(band_names, festival_resolvers)
    logging.info("Bands in lineup: %s", ", ".join(lineup))

    all_songs = {}
    for band in lineup:
        songs = collect_band_songs(
            band,
            copy_last_setlist_threshold=copy_last_setlist_threshold,
            max_setlist_length=max_setlist_length,
            setlist_cache=setlist_cache,
            rate_limiter=rate_limiter,
            force_smart_setlist=force_smart_setlist,
        )
        if songs:
            all_songs[band] = songs

    if not all_songs:
        raise RuntimeError("No songs gathered for any bands in lineup")

    # Create Spotify playlist using gathered songs
    return create_and_populate_playlist(
        all_songs, playlist_name, spotify_cache, sp=None
    )
