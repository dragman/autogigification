from ag.cache import create_null_cache
from ag.clients.spotify import SpotifyClient
from ag.config import SpotifyConfig
from ag.models import Playlist


class FakeSpotipy:
    def __init__(
        self,
        search_results=None,
        artist_results=None,
        album_tracks=None,
    ):
        self.search_results = search_results or []
        self.artist_results = artist_results or []
        self.album_list = []
        self.album_tracks_map = album_tracks or {}
        self.playlist_replace_called = False
        self.added_items = []
        self.artist_search_calls = 0
        self.album_calls = 0
        self.track_calls = 0

    def search(self, q, limit, type):
        if type == "track":
            return {"tracks": {"items": self.search_results}}
        if type == "artist":
            self.artist_search_calls += 1
            return {"artists": {"items": self.artist_results}}
        return {}

    def current_user_playlists(self):
        return {"items": []}

    def user_playlist_create(self, user, name, public=True):
        return {"name": name, "id": "new", "external_urls": {"spotify": "url"}}

    def playlist_replace_items(self, playlist_id, items):
        self.playlist_replace_called = True

    def playlist_add_items(self, playlist_id, items):
        self.added_items.extend(items)

    def artist_albums(self, artist_id, album_type, limit):
        self.album_calls += 1
        return {"items": self.album_list}

    def album_tracks(self, album_id):
        self.track_calls += 1
        return {"items": self.album_tracks_map.get(album_id, [])}


def build_client(fake_spotify):
    cfg = SpotifyConfig(
        client_id="id",
        client_secret="secret",
        redirect_uri="uri",
        username="user",
        refresh_token="token",
        scopes="playlist-modify-public",
        token_cache_path=None,
    )
    return SpotifyClient(cfg, track_cache=create_null_cache(), sp=fake_spotify)


def test_match_is_exact_by_default():
    fake_sp = FakeSpotipy(
        search_results=[
            {"name": "Other Song", "artists": [{"name": "Band"}], "id": "1"},
            {"name": "My Song", "artists": [{"name": "Band"}], "id": "2"},
        ]
    )
    client = build_client(fake_sp)

    _, track_id = client.get_track_id("My Song", "Band")
    assert track_id == "2"

    _, track_id_no = client.get_track_id("Song", "Band")
    assert track_id_no is None


def test_fuzzy_search_opt_in():
    fake_sp = FakeSpotipy(
        search_results=[
            {"name": "My Song (Live)", "artists": [{"name": "Band"}], "id": "live"},
        ]
    )
    client = build_client(fake_sp)

    _, track_id = client.get_track_id("My Song", "Band", use_fuzzy_search=True)
    assert track_id == "live"


def test_populate_playlist_passes_flag():
    fake_sp = FakeSpotipy(
        search_results=[
            {"name": "My Song (Live)", "artists": [{"name": "Band"}], "id": "live"},
        ]
    )
    client = build_client(fake_sp)
    playlist = Playlist(name="p", id="id", url="url")

    client.populate_playlist(
        playlist, {"Band": ["My Song"]}, use_fuzzy_search=True
    )

    assert fake_sp.added_items == ["live"]


def test_discography_fallback_only_when_fuzzy_enabled():
    fake_sp = FakeSpotipy(
        search_results=[],
        artist_results=[{"id": "artist"}],
    )
    fake_sp.album_list = [{"id": "album1"}]
    fake_sp.album_tracks_map = {"album1": [{"id": "t1", "name": "My Song Alt"}]}
    client = build_client(fake_sp)

    # Default: no fuzzy -> no fallback calls, returns None
    _, track_id = client.get_track_id("My Song", "Band", use_fuzzy_search=False)
    assert track_id is None
    assert fake_sp.artist_search_calls == 0

    # Fuzzy enabled: fallback kicks in
    _, track_id = client.get_track_id("My Song", "Band", use_fuzzy_search=True)
    assert track_id == "t1"
    assert fake_sp.artist_search_calls == 1
