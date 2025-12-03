from typing import Tuple
import logging

from ag.impl import create_playlist_from_lineup
from ag.utils.rate_limit import RateLimiter
import click

from ag.cache import create_cache
from ag.setlist import (
    SETLIST_CACHE,
    SPOTIFY_TRACK_CACHE,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


@click.command()
@click.option("--band-names", "-b", multiple=True)
@click.option("--playlist-name")
@click.option(
    "--copy-last-setlist-threshold",
    default=15,
    type=int,
    help="Max age of last setlist (in days)",
)
@click.option(
    "--max-setlist-length", default=12, type=int, help="Max number of songs in setlist"
)
@click.option("--no-cache", is_flag=True, default=False, help="Disable cache")
@click.option(
    "--rate-limit",
    type=float,
    default=1.0,
    help="Rate limit (in seconds), zero for no limit",
)
def main(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    no_cache: bool,
    rate_limit: float,
):
    """Create a Spotify playlist based on the Hellfest lineup."""

    if not band_names:
        raise click.UsageError("Please provide at least one band name.")

    if no_cache:
        setlist_cache = None
        spotify_cache = None
    else:
        setlist_cache = create_cache(SETLIST_CACHE)
        spotify_cache = create_cache(SPOTIFY_TRACK_CACHE)

    rate_limiter = RateLimiter(rate_limit) if rate_limit > 0.0 else None

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


if __name__ == "__main__":
    main()
