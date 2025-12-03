import itertools
import logging
import os
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

import pandas as pd
import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from .cache import Cache, create_cache
from .utils.rate_limit import NullRateLimiter, RateLimiter, retry_after

DEFAULT_SPOTIFY_SCOPES = "playlist-modify-public"

load_dotenv()

SETLIST_FM_API_KEY = os.environ["SETLIST_FM_API_KEY"]
SPOTIFY_API_CREDS = {
    "client_id": os.environ["SPOTIFY_CLIENT_ID"],
    "client_secret": os.environ["SPOTIFY_CLIENT_SECRET"],
    "redirect_uri": os.environ["SPOTIFY_REDIRECT_URI"],
    "refresh_token": os.environ["SPOTIFY_REFRESH_TOKEN"],
}

SPOTIFY_USERNAME = os.environ["SPOTIFY_USERNAME"]

SETLIST_CACHE = os.environ.get("SETLIST_CACHE", "setlist_cache.json")
SPOTIFY_TRACK_CACHE = os.environ.get("SPOTIFY_TRACK_CACHE", "spotify_cache.json")


def get_recent_setlists(
    cache: Cache,
    artist_name: str,
    api_key: Optional[str] = SETLIST_FM_API_KEY,
    rate_limiter: Optional[RateLimiter] = None,
) -> Dict[str, Any]:
    limiter = rate_limiter or NullRateLimiter()
    cached_setlists = cache.get(artist_name)
    if cached_setlists is not None:
        logging.info(f"Using cached setlist for {artist_name}")
        return cached_setlists

    if not api_key:
        raise Exception("API key not set")

    url = (
        f"https://api.setlist.fm/rest/1.0/search/setlists?artistName={artist_name}&p=1"
    )
    headers = {"x-api-key": api_key, "Accept": "application/json"}

    with limiter:
        response = requests.get(url, headers=headers)

    if response.status_code == 429:
        retry_after_seconds = int(response.headers.get("Retry-After", "2"))
        logging.warning(
            "Rate limited fetching setlists for %s. Retrying in %s seconds.",
            artist_name,
            retry_after_seconds,
        )
        with retry_after(retry_after_seconds, limiter):
            response = requests.get(url, headers=headers)

    if response.status_code == 200:
        setlists = response.json()
        cache.set(artist_name, setlists)
        return setlists

    logging.error(response)
    return {}


def extract_common_songs(setlists: Dict[str, Any]) -> List[Tuple[str, pd.Timestamp]]:
    # Example setlist dict
    # {
    #     "type": "setlists",
    #     "itemsPerPage": 20,
    #     "page": 1,
    #     "total": 219,
    #     "setlist": [
    #         {
    #             "eventDate": "25-03-2024",
    #             "lastUpdated": "2024-03-25T23:11:39.361+0000",
    #             "sets": {
    #                 "set": [
    #                     {
    #                         "song": [
    #                             {
    #                                 "name": "Pokemon Theme Song",
    #                                 "tape": true
    #                             },
    #                             {
    #                                 "name": "Dawn"
    #                             },
    #                             {
    #                                 "name": "Demon King"
    #                             },
    #                             {
    #                                 "name": "Lifeblood"
    #                             },
    #                             {
    #                                 "name": "Purge"
    #                             },
    #                             {
    #                                 "name": "Ruin"
    #                             },
    #                             {
    #                                 "name": "Eclipse"
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             },
    #             "info": "Instrumental set due to Kyle Anderson being sick.",
    #         },
    #     ...
    #     ]
    # },

    songs_played_by_date = []
    events = setlists["setlist"]
    for event in events:
        event_date = event["eventDate"]
        url = event["url"]
        for set_i, set_ in enumerate(event["sets"]["set"]):
            songs = set_["song"]
            for song in songs:
                song_name = song.get("name")
                song_is_tape = song.get("tape", False)

                if not song_name:
                    logging.warning(
                        f"No song name in set {set_i} on {event_date=} {url=}"
                    )
                    continue

                if song_is_tape:
                    logging.info(f"{song_name} is a tape, ignoring")
                    continue

                songs_played_by_date.append(
                    (song_name, pd.to_datetime(event_date, dayfirst=True))
                )

            if not songs:
                logging.warning(f"No songs in set {set_i} on {event_date=} {url=}")
                continue

    return songs_played_by_date


def make_spotify() -> spotipy.Spotify:
    auth_manager = create_spotify_auth_manager(show_dialog=False, open_browser=False)
    auth = create_spotify_auth(auth_manager)
    sp = spotipy.Spotify(auth=auth)
    return sp


def create_spotify_auth_manager(
    scope: str = DEFAULT_SPOTIFY_SCOPES,
    show_dialog: bool = True,
    open_browser: bool = True,
) -> SpotifyOAuth:
    """Centralized SpotifyOAuth factory so token flows stay consistent."""
    return SpotifyOAuth(
        client_id=SPOTIFY_API_CREDS["client_id"],
        client_secret=SPOTIFY_API_CREDS["client_secret"],
        redirect_uri=SPOTIFY_API_CREDS["redirect_uri"],
        scope=scope,
        show_dialog=show_dialog,
        open_browser=open_browser,
    )


def create_spotify_auth(auth_manager: SpotifyOAuth) -> Dict[str, Any]:
    token_info = auth_manager.refresh_access_token(SPOTIFY_API_CREDS["refresh_token"])
    return token_info["access_token"]


@dataclass(frozen=True)
class Playlist:
    name: str
    id: str
    url: str

    @classmethod
    def from_spotify(cls, playlist: Dict[str, Any]):
        return cls(
            name=playlist["name"],
            id=playlist["id"],
            url=playlist["external_urls"]["spotify"],
        )


def find_or_create_spotify_playlist(
    sp: spotipy.Spotify, playlist_name: str
) -> Playlist:
    playlists = sp.current_user_playlists()

    if not playlists:
        logging.warning("No playlists found")
    else:
        for playlist in playlists["items"]:
            if playlist and playlist["name"] == playlist_name:
                return Playlist.from_spotify(playlist)

    logging.info(f"Playlist {playlist_name} not found, will create")

    playlist = sp.user_playlist_create(
        user=SPOTIFY_USERNAME, name=playlist_name, public=True
    )

    if not playlist:
        raise Exception("Failed to create playlist")

    return Playlist.from_spotify(playlist)


def populate_spotify_playlist(
    sp: spotipy.Spotify,
    playlist: Playlist,
    songs: Dict[str, List[str]],
    track_cache: Optional[Cache] = None,
) -> None:
    sp.playlist_replace_items(playlist_id=playlist.id, items=[])

    mapped_ids = get_spotify_track_ids(sp, songs, cache=track_cache)
    track_ids = [
        spotify_id
        for _, spotify_id in itertools.chain(*mapped_ids.values())
        if spotify_id is not None
    ]

    # Function to split list into chunks of n
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    # Add tracks to the playlist in batches of 100
    for batch in chunks(track_ids, 100):
        sp.playlist_add_items(playlist_id=playlist.id, items=batch)


def get_spotify_track_ids(
    sp: spotipy.Spotify,
    all_songs: Dict[str, List[str]],
    cache: Optional[Cache] = None,
) -> Dict[str, List[Tuple[str, str]]]:
    track_cache = cache or create_cache(SPOTIFY_TRACK_CACHE)
    track_ids = {}
    for band, songs in all_songs.items():
        for song in songs:
            _, spotify_id = get_spotify_track_id(sp, song, band, track_cache)

            track_ids.setdefault(band, [])
            track_ids[band].append((song, spotify_id))
        logging.info(f"Finished {band}")

    return track_ids


def normalize(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode("utf-8")
        .lower()
    )


def search_track_by_query(
    sp, song: str, band: str, cache: Cache
) -> List[Dict[str, Any]]:
    query = f"{song} {band}"
    cached_results = cache.get(query)
    if cached_results is None:
        results = sp.search(q=query, limit=50, type="track")
        cache.set(query, results)
    else:
        logging.info(f"Using cache for {query}")
        results = cached_results
    return results.get("tracks", {}).get("items", [])


def match_track(tracks: List[Dict[str, Any]], song: str, band: str) -> Optional[str]:
    song_norm = normalize(song)
    band_norm = normalize(band)
    for item in tracks:
        track_name = normalize(item["name"])
        artist_names = [normalize(artist["name"]) for artist in item["artists"]]
        if song_norm in track_name and any(band_norm in a for a in artist_names):
            return item["id"]
    return None


def get_artist_id(sp, band: str) -> Optional[str]:
    results = sp.search(q=band, type="artist", limit=1)
    items = results.get("artists", {}).get("items", [])
    return items[0]["id"] if items else None


def search_track_by_discography(sp, artist_id: str, song: str) -> Optional[str]:
    song_norm = normalize(song)
    albums = sp.artist_albums(artist_id, album_type="album,single", limit=50)
    album_ids = {album["id"] for album in albums["items"]}
    seen_track_ids = set()
    for album_id in album_ids:
        tracks = sp.album_tracks(album_id).get("items", [])
        for track in tracks:
            if track["id"] in seen_track_ids:
                continue
            seen_track_ids.add(track["id"])
            if song_norm in normalize(track["name"]):
                return track["id"]
    return None


def get_spotify_track_id(
    sp,
    song: str,
    band: str,
    spotify_track_cache: Optional[Cache] = None,
) -> Tuple[str, Optional[str]]:
    if not spotify_track_cache:
        spotify_track_cache = create_cache(SPOTIFY_TRACK_CACHE)

    # Try fuzzy search first
    tracks = search_track_by_query(sp, song, band, spotify_track_cache)
    track_id = match_track(tracks, song, band)
    if track_id:
        return song, track_id

    # Fallback: search via artist discography
    logging.warning(f"No match in search results for {band} - {song}, trying fallback")
    artist_id = get_artist_id(sp, band)
    if not artist_id:
        logging.warning(f"Artist not found: {band}")
        return song, None

    track_id = search_track_by_discography(sp, artist_id, song)
    if track_id:
        return song, track_id

    logging.warning(f"No match found anywhere for {band} - {song}")
    return song, None


def derive_song_features(
    songs_by_date: List[Tuple[str, pd.Timestamp]], decay_rate: float
) -> pd.DataFrame:
    names, dates = zip(*songs_by_date)
    df = pd.DataFrame({"name": names, "date": dates})

    days_since_played = (pd.Timestamp.now() - df["date"]).dt.days  # type: ignore
    df["weight"] = decay_rate ** (days_since_played / 30)

    df["position"] = df.groupby("date").cumcount() + 1
    df["setlist_size"] = df.groupby("date")["name"].transform("count")

    df["is_first"] = df["position"] == 1
    df["is_last"] = df["position"] == df["setlist_size"]

    return df


def extract_last_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]],
) -> Tuple[List[str], pd.Timestamp]:
    songs, dates = zip(*songs_by_date)
    song_series = pd.Series(songs, index=dates)
    song_series = song_series.sort_index(ascending=False)
    last_date: pd.Timestamp = song_series.index[0]  # type: ignore
    last_setlist = song_series.loc[last_date]

    if len(last_setlist) < 5:
        logging.info(f"Less than 5 songs played on {last_date}")

    return list(last_setlist), last_date


def extract_smart_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]], setlist_length: int
) -> List[str]:
    # Given a desired setlist length, find the most frequently played songs according to features
    df = derive_song_features(songs_by_date, decay_rate=0.9)

    # Find relative positions of songs in setlist
    df["normalised_position"] = df["position"] / df["setlist_size"]

    # Create position bins
    position_bins = [0, 0.2, 0.8, 1]
    position_labels = ["Start", "Middle", "End"]
    df["position_bin"] = pd.cut(
        df["normalised_position"], bins=position_bins, labels=position_labels
    )

    # Create frequency table of positions scaled by recency
    weighted_position_freq = (
        df.groupby(["position_bin", "name"], observed=True)["weight"]
        .sum()
        .unstack(fill_value=0)
    )

    all_songs = set()
    setlist = []

    # Find first and last songs
    most_likely_first = df.loc[df["is_first"]].groupby("name")["weight"].sum().idxmax()
    most_likely_last = df.loc[df["is_last"]].groupby("name")["weight"].sum().idxmax()

    all_songs = {most_likely_first, most_likely_last}
    setlist = [most_likely_first]

    # Fill middle in order according to position bin
    for i in range(2, setlist_length):
        current_bin = position_labels[i // setlist_length]
        remaining_songs_position_freq = weighted_position_freq.loc[
            current_bin,
            [song for song in weighted_position_freq.columns if song not in all_songs],
        ]  # type: ignore

        most_likely_song = remaining_songs_position_freq.idxmax()
        setlist.append(most_likely_song)
        all_songs.add(most_likely_song)

    setlist.append(most_likely_last)

    return setlist  # type: ignore
