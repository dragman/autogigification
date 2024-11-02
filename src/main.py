from typing import Tuple
import click

import pandas as pd

from hellfest import get_hellfest_lineup
from setlist import (
    SETLIST_CACHE,
    create_spotify_playlist,
    extract_common_songs,
    extract_last_setlist,
    extract_smart_setlist,
    get_recent_setlists,
    load_cache,
)


@click.command()
@click.option("--band-names", "-b", multiple=True)
@click.option("--playlist-name")
@click.option(
    "--copy-last-setlist-threshold",
    default=7,
    type=int,
    help="Max age of last setlist (in days)",
)
@click.option(
    "--max-setlist-length", default=12, type=int, help="Max number of songs in setlist"
)
def do_it(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
):
    """Create a Spotify playlist based on the Hellfest lineup."""

    if not band_names:
        raise click.UsageError("Please provide at least one band name.")

    setlist_cache = load_cache(SETLIST_CACHE)

    all_songs = {}

    for band_name in band_names:
        # Hellfest data
        if band_name.lower() == "hellfest":
            lineup = get_hellfest_lineup()
            if not lineup:
                raise click.UsageError("Failed to get Hellfest lineup.")
        else:
            lineup = [band_name]

        click.echo(f"Bands in lineup: {', '.join(lineup)}")
        # Fetch and aggregate songs from Setlist.fm
        for band in lineup:
            setlists = get_recent_setlists(setlist_cache, band)

            if setlists:
                songs_by_date = extract_common_songs(setlists)

                songs, last_date = extract_last_setlist(songs_by_date)
                last_setlist_age = (pd.Timestamp.now() - last_date).days

                if last_setlist_age > copy_last_setlist_threshold:
                    click.echo(
                        f"{band}: Last setlist {last_date} is {last_setlist_age} days old. Smart setlist will be used."
                    )
                    songs = extract_smart_setlist(songs_by_date, max_setlist_length)
                else:
                    click.echo(
                        f"{band}: Last setlist {last_date} is fresh. Using last setlist."
                    )

                click.echo(f"{band}: {len(songs)} songs")
                all_songs[band] = list(set(songs))[:max_setlist_length]
            else:
                click.echo(f"No setlists found for {band}", err=True)

        # Create Spotify playlist
        playlist_url = create_spotify_playlist(playlist_name, all_songs)
        click.echo(f"Playlist created: {playlist_url}")


if __name__ == "__main__":
    do_it()
