from typing import Tuple
import logging

import click

from ag.run import run_playlist_job

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

    try:
        playlist = run_playlist_job(
            band_names,
            playlist_name,
            copy_last_setlist_threshold,
            max_setlist_length,
            no_cache=no_cache,
            rate_limit=rate_limit,
        )
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc


if __name__ == "__main__":
    main()
