from typing import Tuple
import logging
import json
import os

import click
from dotenv import load_dotenv

from ag.run import playlist_result_to_payload, run_playlist_job

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment when running via CLI so config is available for services.
load_dotenv()

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
@click.option(
    "--fuzzy",
    is_flag=True,
    default=False,
    help="Enable fuzzy track name matching (default off).",
)
@click.option(
    "--no-playlist",
    is_flag=True,
    default=False,
    help="Skip playlist creation and just print the setlist + track links.",
)
@click.option(
    "--force-smart-setlist",
    is_flag=True,
    default=False,
    help="Always estimate the setlist even if a fresh one exists.",
)
def main(
    band_names: Tuple[str, ...],
    playlist_name: str,
    copy_last_setlist_threshold: int,
    max_setlist_length: int,
    no_cache: bool,
    rate_limit: float,
    fuzzy: bool,
    no_playlist: bool,
    force_smart_setlist: bool,
):
    """Create a Spotify playlist based on the Hellfest lineup."""

    force_smart = True if force_smart_setlist else None
    spotify_user_creds_present = all(
        (
            os.environ.get("SPOTIFY_REFRESH_TOKEN"),
            os.environ.get("SPOTIFY_USERNAME"),
            os.environ.get("SPOTIFY_REDIRECT_URI"),
        )
    )
    create_playlist = not no_playlist and spotify_user_creds_present

    if not no_playlist and not spotify_user_creds_present:
        logging.info(
            "Spotify user token missing, running in preview-only mode (no playlist creation)."
        )
    try:
        result = run_playlist_job(
            band_names,
            playlist_name,
            copy_last_setlist_threshold,
            max_setlist_length,
            no_cache=no_cache,
            rate_limit=rate_limit,
            use_fuzzy_search=fuzzy,
            create_playlist=create_playlist,
            force_smart_setlist=force_smart,
        )
        payload = playlist_result_to_payload(result)
        click.echo(json.dumps(payload, indent=2))
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc


if __name__ == "__main__":
    main()
