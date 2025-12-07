import pandas as pd

from ag.models import Playlist, SongMatch
from ag.services.lineup import resolve_lineup
from ag.services.playlist_builder import BandSetlistPlan, PlaylistBuilder


class DummySetlistClient:
    def __init__(self, payload):
        self.payload = payload

    def get_recent_setlists(self, artist_name: str):
        return self.payload.get(artist_name, {})


class DummySpotifyClient:
    def __init__(self):
        self.calls = {}

    def find_or_create_playlist(self, playlist_name: str):
        self.calls["playlist_name"] = playlist_name
        return Playlist(name=playlist_name, id="123", url="http://example")

    def populate_playlist(self, playlist: Playlist, songs, **kwargs):
        self.calls["playlist"] = playlist
        self.calls["songs"] = songs
        self.calls["mapped_tracks"] = kwargs.get("mapped_tracks")

    def map_tracks(self, all_songs, **kwargs):
        self.calls["map_tracks"] = {"songs": all_songs, **kwargs}
        mapped = {}
        for band, songs in all_songs.items():
            mapped[band] = [
                SongMatch(
                    name=song,
                    spotify_id=f"{band}-{i}",
                    spotify_url=f"url-{band}-{i}",
                    status="found",
                    strategy="exact",
                )
                for i, song in enumerate(songs)
            ]
        return mapped


def test_resolve_lineup_mixes_festival_and_direct():
    calls = {}

    def fake_festival():
        calls["invoked"] = True
        return ["Band A", "Band B"]

    lineup = resolve_lineup(["Hellfest", "Custom Band"], {"hellfest": fake_festival})

    assert calls["invoked"] is True
    assert lineup == ["Band A", "Band B", "Custom Band"]


def test_collect_band_songs_returns_none_when_no_setlists(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {}}),
        DummySpotifyClient(),
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=15,
        max_setlist_length=10,
    )

    assert songs is None


def test_collect_band_songs_uses_last_setlist(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {"data": 1}}),
        DummySpotifyClient(),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_common_songs",
        lambda setlists: ["songs"],
    )

    recent_date = pd.Timestamp.now()
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_last_setlist",
        lambda songs_by_date: (["song1", "song2"], recent_date),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_smart_setlist",
        lambda songs_by_date, max_len: ["smart"],
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=10_000,
        max_setlist_length=10,
    )

    assert songs
    assert songs.songs == ["song1", "song2"]
    assert songs.setlist_type == "fresh"


def test_collect_band_songs_uses_smart_setlist_when_stale(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {"data": 1}}),
        DummySpotifyClient(),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_common_songs",
        lambda setlists: ["songs"],
    )
    stale_date = pd.Timestamp("2020-01-01")
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_last_setlist",
        lambda songs_by_date: (["old"], stale_date),
    )

    smart_songs = ["smart1", "smart2"]
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_smart_setlist",
        lambda songs_by_date, max_len: smart_songs,
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1,
        max_setlist_length=10,
    )

    assert songs
    assert songs.songs == smart_songs
    assert songs.setlist_type == "estimated"


def test_collect_band_songs_respects_force_smart_true(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {"data": 1}}),
        DummySpotifyClient(),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_common_songs",
        lambda setlists: ["songs"],
    )
    recent_date = pd.Timestamp.now()
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_last_setlist",
        lambda songs_by_date: (["old"], recent_date),
    )

    smart_songs = ["smart1"]
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_smart_setlist",
        lambda songs_by_date, max_len: smart_songs,
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1000,
        max_setlist_length=10,
        force_smart_setlist=True,
    )

    assert songs
    assert songs.songs == smart_songs
    assert songs.setlist_type == "estimated"


def test_collect_band_songs_respects_force_smart_false(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {"data": 1}}),
        DummySpotifyClient(),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_common_songs",
        lambda setlists: ["songs"],
    )
    stale_date = pd.Timestamp("2020-01-01")
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_last_setlist",
        lambda songs_by_date: (["old", "older"], stale_date),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_smart_setlist",
        lambda songs_by_date, max_len: ["smart"],
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1,
        max_setlist_length=10,
        force_smart_setlist=False,
    )

    assert songs
    assert songs.songs == ["old", "older"]
    assert songs.setlist_type == "fresh"


def test_collect_band_songs_handles_future_date(monkeypatch):
    builder = PlaylistBuilder(
        DummySetlistClient({"Band": {"data": 1}}),
        DummySpotifyClient(),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_common_songs",
        lambda setlists: ["songs"],
    )
    future_date = pd.Timestamp.now() + pd.Timedelta(days=10)
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_last_setlist",
        lambda songs_by_date: (["future"], future_date),
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.extract_smart_setlist",
        lambda songs_by_date, max_len: ["smart-future"],
    )

    songs = builder._collect_band_songs(
        "Band",
        copy_last_setlist_threshold=15,
        max_setlist_length=10,
    )

    assert songs
    assert songs.setlist_type == "estimated"
    assert songs.songs == ["smart-future"]


def test_build_playlist_orchestrates(monkeypatch):
    dummy_spotify = DummySpotifyClient()
    builder = PlaylistBuilder(
        DummySetlistClient({"BandX": {"data": 1}}),
        dummy_spotify,
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.resolve_lineup",
        lambda band_names, resolvers: ["BandX"],
    )
    monkeypatch.setattr(
        builder,
        "_collect_band_songs",
        lambda band, **kwargs: BandSetlistPlan(
            band=band,
            songs=["song1", "song2"],
            setlist_type="fresh",
            setlist_date=pd.Timestamp("2024-01-01"),
            last_setlist_age_days=2,
        ),
    )

    result = builder.build_playlist(
        ("BandX",),
        "My Playlist",
        copy_last_setlist_threshold=5,
        max_setlist_length=10,
    )

    assert result.playlist
    assert result.playlist.name == "My Playlist"
    assert result.created_playlist is True
    assert dummy_spotify.calls["playlist_name"] == "My Playlist"
    assert dummy_spotify.calls["songs"] == {"BandX": ["song1", "song2"]}
    assert dummy_spotify.calls["mapped_tracks"]["BandX"][0].name == "song1"
    assert result.setlists[0].setlist_type == "fresh"
    assert result.setlists[0].songs[0].spotify_id == "BandX-0"


def test_build_playlist_preview_mode(monkeypatch):
    dummy_spotify = DummySpotifyClient()
    builder = PlaylistBuilder(
        DummySetlistClient({"BandY": {"data": 1}}),
        dummy_spotify,
    )
    monkeypatch.setattr(
        "ag.services.playlist_builder.resolve_lineup",
        lambda band_names, resolvers: ["BandY"],
    )
    monkeypatch.setattr(
        builder,
        "_collect_band_songs",
        lambda band, **kwargs: BandSetlistPlan(
            band=band,
            songs=["song3"],
            setlist_type="estimated",
            setlist_date=pd.Timestamp("2024-02-01"),
            last_setlist_age_days=30,
        ),
    )

    result = builder.build_playlist(
        ("BandY",),
        "Preview Playlist",
        copy_last_setlist_threshold=5,
        max_setlist_length=10,
        create_playlist=False,
    )

    assert result.playlist is None
    assert result.created_playlist is False
    assert dummy_spotify.calls["map_tracks"]["songs"]["BandY"] == ["song3"]
    assert "playlist_name" not in dummy_spotify.calls
