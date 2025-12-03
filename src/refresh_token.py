import logging

import click
from dotenv import load_dotenv

from ag.setlist import (
    DEFAULT_SPOTIFY_SCOPES,
    create_spotify_auth,
    create_spotify_auth_manager,
)

load_dotenv()


@click.command()
@click.option(
    "--scope",
    default=DEFAULT_SPOTIFY_SCOPES,
    show_default=True,
    help="Spotify scopes to request (space separated).",
)
def main(scope: str):
    """Obtain and print a Spotify refresh token using the configured credentials."""
    auth_manager = create_spotify_auth_manager(
        scope, show_dialog=True, open_browser=True
    )
    token_info = auth_manager.get_access_token(as_dict=True)
    refresh_token = token_info.get("refresh_token")
    if not refresh_token:
        raise RuntimeError(
            "No refresh token returned. Ensure you've completed the auth flow and requested offline access."
        )

    logging.info("Access token expires at %s", token_info.get("expires_at"))
    click.echo(refresh_token)


if __name__ == "__main__":
    main()
