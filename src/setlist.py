import itertools
import json
import os
import time
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

SETLIST_FM_API_KEY = os.environ["SETLIST_FM_API_KEY"]
SPOTIFY_API_CREDS = {
    "client_id": os.environ["SPOTIFY_CLIENT_ID"],
    "client_secret": os.environ["SPOTIFY_CLIENT_SECRET"],
    "redirect_uri": os.environ["SPOTIFY_REDIRECT_URI"],
}

SPOTIFY_USERNAME = os.environ["SPOTIFY_USERNAME"]

SETLIST_CACHE = os.environ["SETLIST_CACHE"]
SPOTIFY_TRACK_CACHE = os.environ["SPOTIFY_TRACK_CACHE"]


def load_cache(cache_path: str):
    if os.path.exists(cache_path):
        with open(cache_path, "r") as file:
            return json.load(file)
    return {}


def save_cache(cache_path: str, cache: Dict[str, Any]):
    with open(cache_path, "w") as file:
        json.dump(cache, file, indent=4)
        print(file.name)


def load_setlist_cache():
    return load_cache(SETLIST_CACHE)


def load_spotify_track_cache():
    return load_cache(SPOTIFY_TRACK_CACHE)


def get_recent_setlists(
    cache: Dict[str, Any], artist_name: str, api_key=SETLIST_FM_API_KEY
):
    if artist_name in cache:
        print(f"Using cached setlist for {artist_name}")
        return cache[artist_name]

    url = (
        f"https://api.setlist.fm/rest/1.0/search/setlists?artistName={artist_name}&p=1"
    )
    headers = {"x-api-key": api_key, "Accept": "application/json"}

    time.sleep(1)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        setlists = response.json()
        cache[artist_name] = setlists
        save_cache(SETLIST_CACHE, cache)
        return setlists
    else:
        print(response)


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

    # Given a list of recent setlist by band, use a smart algorithm to guess what's most likely to be played.

    # Make a dataframe of all setlist information

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
                    print(f"No song name in set {set_i} on {event_date=} {url=}")
                    continue

                if song_is_tape:
                    print(f"{song_name} is a tape, ignoring")
                    continue

                songs_played_by_date.append(
                    (song_name, pd.to_datetime(event_date, dayfirst=True))
                )

            if not songs:
                print(f"No songs in set {set_i} on {event_date=} {url=}")
                continue

    return songs_played_by_date


def make_spotify():
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_API_CREDS["client_id"],
            client_secret=SPOTIFY_API_CREDS["client_secret"],
            redirect_uri=SPOTIFY_API_CREDS["redirect_uri"],
            scope="playlist-modify-public",
        )
    )
    return sp


def create_spotify_playlist(playlist_name: str, songs: Dict[str, List[str]]):
    sp = make_spotify()

    playlist = sp.user_playlist_create(
        user=SPOTIFY_USERNAME, name=playlist_name, public=True
    )

    if not playlist:
        print("Failed to create playlist")
        return

    mapped_ids = get_spotify_track_ids(songs)
    track_ids = [
        spotify_id
        for _, spotify_id in itertools.chain(*mapped_ids.values())
        if spotify_id is not None
    ]
    # sp.user_playlist_add_tracks(user=username, playlist_id=playlist['id'], tracks=track_ids)

    # Function to split list into chunks of n
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    # Add tracks to the playlist in batches of 100
    for batch in chunks(track_ids, 100):
        sp.playlist_add_items(playlist_id=playlist["id"], items=batch)

    return playlist["external_urls"]["spotify"]


def get_spotify_track_ids(
    all_songs: Dict[str, List[str]],
) -> Dict[str, List[Tuple[str, str]]]:
    sp = make_spotify()
    track_ids = {}
    spotify_track_cache = load_cache(SPOTIFY_TRACK_CACHE)
    for band, songs in all_songs.items():
        any_writes = False
        for song in songs:
            search_term = f"{song} {band}"
            if search_term not in spotify_track_cache:
                results = sp.search(q=search_term, limit=1, type="track")
                if not results:
                    print(f"No results for {search_term}")
                    continue

                print(f'Got {len(results["tracks"]["items"])} tracks for {search_term}')
                spotify_track_cache[search_term] = results
                any_writes = True
            else:
                print(f"Using cache for {search_term}")
                results = spotify_track_cache[search_term]

            if results["tracks"]["items"]:
                spotify_id = results["tracks"]["items"][0]["id"]
            else:
                print(f"No spotify track found for {band} - {song}")
                spotify_id = None

            track_ids.setdefault(band, [])
            track_ids[band].append((song, spotify_id))
        print(f"Finished {band}")

        if any_writes:
            save_cache(SPOTIFY_TRACK_CACHE, spotify_track_cache)

    return track_ids


def extract_last_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]],
) -> Tuple[List[str], pd.Timestamp]:
    songs, dates = zip(*songs_by_date)
    song_series = pd.Series(songs, index=dates)
    song_series = song_series.sort_index(ascending=False)
    last_date: pd.Timestamp = song_series.index[0]
    last_setlist = song_series.loc[last_date]

    if len(last_setlist) < 5:
        print(f"Less than 5 songs played on {last_date}")

    return list(last_setlist), last_date


def extract_smart_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]], setlist_length: int
) -> List[str]:
    names, dates = zip(*songs_by_date)
    df = pd.DataFrame({"name": names, "date": dates})

    # Make weighted song frequencies
    days_since_played = (pd.Timestamp.now() - df["date"]).dt.days
    decay_rate = 0.9
    df["weight"] = decay_rate ** (days_since_played / 30)

    weighted_songs = df.groupby("name")["weight"].sum()
    weighted_songs = weighted_songs.sort_values(ascending=False)

    print(weighted_songs)

    return list(weighted_songs.iloc[:setlist_length].index)
