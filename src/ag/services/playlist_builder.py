import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from ag.clients.setlist_fm import SetlistFmClient
from ag.clients.spotify import SpotifyClient
from ag.models import Playlist, PlaylistBuildResult, SetlistResult
from ag.services.setlist_selection import (
    extract_common_songs,
    extract_last_setlist,
    extract_smart_setlist,
    should_use_smart_setlist,
)


@dataclass
class BandSetlistPlan:
    band: str
    songs: List[str]
    setlist_type: str  # "fresh" | "estimated"
    setlist_date: Optional[pd.Timestamp]
    last_setlist_age_days: Optional[int]


class PlaylistBuilder:
    """Orchestrates fetching setlists, selecting songs, and populating Spotify playlists."""

    def __init__(
        self,
        setlist_client: SetlistFmClient,
        spotify_client: SpotifyClient,
    ):
        self.setlist_client = setlist_client
        self.spotify_client = spotify_client

    def _collect_band_songs(
        self,
        band: str,
        *,
        copy_last_setlist_threshold: int,
        max_setlist_length: int,
        force_smart_setlist: Optional[bool] = None,
    ) -> Optional[BandSetlistPlan]:
        setlists = self.setlist_client.get_recent_setlists(band)
        if not setlists:
            logging.warning("No setlists found for %s", band)
            return None

        songs_by_date = extract_common_songs(setlists)
        if not songs_by_date:
            logging.warning("No songs found in setlists for %s", band)
            return None

        songs, last_date = extract_last_setlist(songs_by_date)
        raw_age_days = (pd.Timestamp.now() - last_date).days
        if raw_age_days < 0:
            logging.warning(
                "%s: Last setlist date %s is in the future, treating as stale/estimated",
                band,
                last_date,
            )
            last_setlist_age = raw_age_days
        else:
            last_setlist_age = raw_age_days

        if force_smart_setlist is True:
            use_smart = True
        elif raw_age_days < 0:
            use_smart = True
        else:
            use_smart = should_use_smart_setlist(
                last_setlist_age, copy_last_setlist_threshold
            )

        if use_smart:
            logging.info(
                "%s: Last setlist %s is %s days old. Smart setlist will be used.",
                band,
                last_date,
                last_setlist_age,
            )
            songs = extract_smart_setlist(songs_by_date, max_setlist_length)
            setlist_type = "estimated"
        else:
            logging.info(
                "%s: Last setlist %s is fresh. Using last setlist.",
                band,
                last_date,
            )
            setlist_type = "fresh"

        logging.info("%s: %s songs", band, len(songs))
        return BandSetlistPlan(
            band=band,
            songs=songs,
            setlist_type=setlist_type,
            setlist_date=last_date,
            last_setlist_age_days=max(last_setlist_age, 0),
        )

    def build_playlist(
        self,
        band_names: Iterable[str],
        playlist_name: Optional[str],
        copy_last_setlist_threshold: int,
        max_setlist_length: int,
        *,
        force_smart_setlist: Optional[bool] = None,
        use_fuzzy_search: bool = False,
        create_playlist: bool = True,
    ) -> PlaylistBuildResult:
        if create_playlist and not playlist_name:
            raise ValueError("playlist_name is required when creating a playlist")

        lineup = list(band_names)
        logging.info("Bands in lineup: %s", ", ".join(lineup))

        setlist_plans: List[BandSetlistPlan] = []
        for band in lineup:
            plan = self._collect_band_songs(
                band,
                copy_last_setlist_threshold=copy_last_setlist_threshold,
                max_setlist_length=max_setlist_length,
                force_smart_setlist=force_smart_setlist,
            )
            if plan:
                setlist_plans.append(plan)

        if not setlist_plans:
            raise RuntimeError("No songs gathered for any bands in lineup")

        songs_by_band: Dict[str, List[str]] = {
            plan.band: plan.songs for plan in setlist_plans
        }
        mapped_tracks = self.spotify_client.map_tracks(
            songs_by_band, use_fuzzy_search=use_fuzzy_search
        )

        setlist_results = [
            SetlistResult(
                band=plan.band,
                setlist_type=plan.setlist_type,
                setlist_date=plan.setlist_date.date().isoformat()
                if plan.setlist_date is not None
                else None,
                last_setlist_age_days=plan.last_setlist_age_days,
                songs=mapped_tracks.get(plan.band, []),
            )
            for plan in setlist_plans
        ]

        playlist: Optional[Playlist] = None
        if create_playlist:
            playlist = self.spotify_client.find_or_create_playlist(playlist_name)
            self.spotify_client.populate_playlist(
                playlist,
                songs_by_band,
                use_fuzzy_search=use_fuzzy_search,
                mapped_tracks=mapped_tracks,
            )

        return PlaylistBuildResult(
            setlists=setlist_results,
            playlist=playlist,
            created_playlist=playlist is not None,
        )
