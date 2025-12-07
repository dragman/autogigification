import logging
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ag.clients.setlist_fm import SetlistFmClient
from ag.clients.spotify import SpotifyClient
from ag.models import Playlist
from ag.services.lineup import DEFAULT_FESTIVAL_RESOLVERS, resolve_lineup
from ag.services.setlist_selection import (
    extract_common_songs,
    extract_last_setlist,
    extract_smart_setlist,
    should_use_smart_setlist,
)


class PlaylistBuilder:
    """Orchestrates fetching setlists, selecting songs, and populating Spotify playlists."""

    def __init__(
        self,
        setlist_client: SetlistFmClient,
        spotify_client: SpotifyClient,
        *,
        festival_resolvers=None,
    ):
        self.setlist_client = setlist_client
        self.spotify_client = spotify_client
        self.festival_resolvers = festival_resolvers or DEFAULT_FESTIVAL_RESOLVERS

    def _collect_band_songs(
        self,
        band: str,
        *,
        copy_last_setlist_threshold: int,
        max_setlist_length: int,
        force_smart_setlist: Optional[bool] = None,
    ) -> Optional[List[str]]:
        setlists = self.setlist_client.get_recent_setlists(band)
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

    def build_playlist(
        self,
        band_names: Iterable[str],
        playlist_name: str,
        copy_last_setlist_threshold: int,
        max_setlist_length: int,
        *,
        force_smart_setlist: Optional[bool] = None,
        use_fuzzy_search: bool = False,
    ) -> Playlist:
        lineup = resolve_lineup(band_names, self.festival_resolvers)
        logging.info("Bands in lineup: %s", ", ".join(lineup))

        all_songs: Dict[str, List[str]] = {}
        for band in lineup:
            songs = self._collect_band_songs(
                band,
                copy_last_setlist_threshold=copy_last_setlist_threshold,
                max_setlist_length=max_setlist_length,
                force_smart_setlist=force_smart_setlist,
            )
            if songs:
                all_songs[band] = songs

        if not all_songs:
            raise RuntimeError("No songs gathered for any bands in lineup")

        playlist = self.spotify_client.find_or_create_playlist(playlist_name)
        self.spotify_client.populate_playlist(
            playlist, all_songs, use_fuzzy_search=use_fuzzy_search
        )
        return playlist
