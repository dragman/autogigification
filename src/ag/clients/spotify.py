import itertools
import logging
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from ag.cache import Cache
from ag.config import SpotifyConfig
from ag.models import Playlist

DEFAULT_SPOTIFY_SCOPES = "playlist-modify-public"


def normalize(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


class SpotifyClient:
    """Small wrapper around spotipy with caching and ID resolution helpers."""

    def __init__(
        self,
        config: SpotifyConfig,
        track_cache: Cache,
        sp: Optional[spotipy.Spotify] = None,
    ):
        self.config = config
        self.track_cache = track_cache
        self._sp = sp

    def create_auth_manager(
        self,
        scope: str = DEFAULT_SPOTIFY_SCOPES,
        show_dialog: bool = True,
        open_browser: bool = True,
    ) -> SpotifyOAuth:
        return SpotifyOAuth(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            redirect_uri=self.config.redirect_uri,
            scope=scope,
            show_dialog=show_dialog,
            open_browser=open_browser,
            cache_path=self.config.token_cache_path,
        )

    def _ensure_client(self) -> spotipy.Spotify:
        if self._sp is None:
            auth_manager = self.create_auth_manager(
                scope=self.config.scopes,
                show_dialog=False,
                open_browser=False,
            )
            token_info = auth_manager.refresh_access_token(self.config.refresh_token)
            access_token = token_info["access_token"]
            self._sp = spotipy.Spotify(auth=access_token)
        return self._sp

    @property
    def sp(self) -> spotipy.Spotify:
        return self._ensure_client()

    def find_or_create_playlist(self, playlist_name: str) -> Playlist:
        playlists = self.sp.current_user_playlists()

        if playlists:
            for playlist in playlists["items"]:
                if playlist and playlist["name"] == playlist_name:
                    return Playlist.from_spotify(playlist)

        logging.info("Playlist %s not found, will create", playlist_name)
        playlist = self.sp.user_playlist_create(
            user=self.config.username, name=playlist_name, public=True
        )
        if not playlist:
            raise RuntimeError("Failed to create playlist")
        return Playlist.from_spotify(playlist)

    def _search_track_by_query(
        self, song: str, band: str
    ) -> List[Dict[str, Any]]:
        query = f"{song} {band}"
        cached_results = self.track_cache.get(query)
        if cached_results is None:
            results = self.sp.search(q=query, limit=50, type="track")
            self.track_cache.set(query, results)
        else:
            logging.info("Using cache for %s", query)
            results = cached_results
        return results.get("tracks", {}).get("items", [])

    def _match_track(
        self,
        tracks: List[Dict[str, Any]],
        song: str,
        band: str,
        *,
        fuzzy: bool = False,
    ) -> Optional[str]:
        song_norm = normalize(song)
        band_norm = normalize(band)
        for item in tracks:
            track_name = normalize(item["name"])
            artist_names = [normalize(artist["name"]) for artist in item["artists"]]
            name_match = song_norm in track_name if fuzzy else song_norm == track_name
            if name_match and any(band_norm in a for a in artist_names):
                return item["id"]
        return None

    def _get_artist_id(self, band: str) -> Optional[str]:
        results = self.sp.search(q=band, type="artist", limit=1)
        items = results.get("artists", {}).get("items", [])
        return items[0]["id"] if items else None

    def _search_track_by_discography(self, artist_id: str, song: str) -> Optional[str]:
        song_norm = normalize(song)
        albums = self.sp.artist_albums(artist_id, album_type="album,single", limit=50)
        album_ids = {album["id"] for album in albums["items"]}
        seen_track_ids = set()
        for album_id in album_ids:
            tracks = self.sp.album_tracks(album_id).get("items", [])
            for track in tracks:
                if track["id"] in seen_track_ids:
                    continue
                seen_track_ids.add(track["id"])
                if song_norm in normalize(track["name"]):
                    return track["id"]
        return None

    def get_track_id(
        self, song: str, band: str, *, use_fuzzy_search: bool = False
    ) -> Tuple[str, Optional[str]]:
        tracks = self._search_track_by_query(song, band)
        track_id = self._match_track(tracks, song, band, fuzzy=use_fuzzy_search)
        if track_id:
            return song, track_id

        if not use_fuzzy_search:
            logging.warning(
                "No exact match in search results for %s - %s (fuzzy off)", band, song
            )
            return song, None

        logging.warning(
            "No match in search results for %s - %s, trying fallback", band, song
        )
        artist_id = self._get_artist_id(band)
        if not artist_id:
            logging.warning("Artist not found: %s", band)
            return song, None

        track_id = self._search_track_by_discography(artist_id, song)
        if track_id:
            return song, track_id

        logging.warning("No match found anywhere for %s - %s", band, song)
        return song, None

    def map_tracks(
        self,
        all_songs: Dict[str, List[str]],
        *,
        use_fuzzy_search: bool = False,
    ) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        mapped: Dict[str, List[Tuple[str, Optional[str]]]] = {}
        for band, songs in all_songs.items():
            for song in songs:
                _, track_id = self.get_track_id(
                    song, band, use_fuzzy_search=use_fuzzy_search
                )
                mapped.setdefault(band, [])
                mapped[band].append((song, track_id))
            logging.info("Finished mapping tracks for %s", band)
        return mapped

    def populate_playlist(
        self,
        playlist: Playlist,
        songs: Dict[str, List[str]],
        *,
        use_fuzzy_search: bool = False,
    ) -> None:
        self.sp.playlist_replace_items(playlist_id=playlist.id, items=[])

        mapped_ids = self.map_tracks(songs, use_fuzzy_search=use_fuzzy_search)
        track_ids = [
            spotify_id
            for _, spotify_id in itertools.chain(*mapped_ids.values())
            if spotify_id is not None
        ]

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        for batch in chunks(track_ids, 100):
            self.sp.playlist_add_items(playlist_id=playlist.id, items=batch)
