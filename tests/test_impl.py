import pandas as pd
import pytest

from ag import impl
from ag.cache import create_null_cache


def test_resolve_lineup_mixes_festival_and_direct():
    calls = {}

    def fake_festival():
        calls["invoked"] = True
        return ["Band A", "Band B"]

    lineup = impl.resolve_lineup(
        ["Hellfest", "Custom Band"], {"hellfest": fake_festival}
    )

    assert calls["invoked"] is True
    assert lineup == ["Band A", "Band B", "Custom Band"]


def test_collect_band_songs_returns_none_when_no_setlists(monkeypatch):
    monkeypatch.setattr(impl, "get_recent_setlists", lambda cache, band, **kwargs: {})

    songs = impl.collect_band_songs(
        "Band", copy_last_setlist_threshold=15, max_setlist_length=10, setlist_cache=create_null_cache()
    )

    assert songs is None


def test_collect_band_songs_uses_last_setlist(monkeypatch):
    monkeypatch.setattr(
        impl, "get_recent_setlists", lambda cache, band, **kwargs: {"data": 1}
    )
    monkeypatch.setattr(impl, "extract_common_songs", lambda setlists: ["songs"])

    recent_date = pd.Timestamp.now()
    monkeypatch.setattr(
        impl, "extract_last_setlist", lambda songs_by_date: (["song1", "song2"], recent_date)
    )
    monkeypatch.setattr(impl, "extract_smart_setlist", lambda songs_by_date, max_len: ["smart"])

    songs = impl.collect_band_songs(
        "Band",
        copy_last_setlist_threshold=10_000,
        max_setlist_length=10,
        setlist_cache=create_null_cache(),
    )

    assert songs == ["song1", "song2"]


def test_collect_band_songs_uses_smart_setlist_when_stale(monkeypatch):
    monkeypatch.setattr(
        impl, "get_recent_setlists", lambda cache, band, **kwargs: {"data": 1}
    )
    monkeypatch.setattr(impl, "extract_common_songs", lambda setlists: ["songs"])
    stale_date = pd.Timestamp("2020-01-01")
    monkeypatch.setattr(
        impl, "extract_last_setlist", lambda songs_by_date: (["old"], stale_date)
    )

    smart_songs = ["smart1", "smart2"]
    monkeypatch.setattr(
        impl, "extract_smart_setlist", lambda songs_by_date, max_len: smart_songs
    )

    songs = impl.collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1,
        max_setlist_length=10,
        setlist_cache=create_null_cache(),
    )

    assert songs == smart_songs


def test_collect_band_songs_respects_force_smart_true(monkeypatch):
    monkeypatch.setattr(
        impl, "get_recent_setlists", lambda cache, band, **kwargs: {"data": 1}
    )
    monkeypatch.setattr(impl, "extract_common_songs", lambda setlists: ["songs"])
    recent_date = pd.Timestamp.now()
    monkeypatch.setattr(
        impl, "extract_last_setlist", lambda songs_by_date: (["old"], recent_date)
    )

    smart_songs = ["smart1"]
    monkeypatch.setattr(
        impl, "extract_smart_setlist", lambda songs_by_date, max_len: smart_songs
    )

    songs = impl.collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1000,
        max_setlist_length=10,
        setlist_cache=create_null_cache(),
        force_smart_setlist=True,
    )

    assert songs == smart_songs


def test_collect_band_songs_respects_force_smart_false(monkeypatch):
    monkeypatch.setattr(
        impl, "get_recent_setlists", lambda cache, band, **kwargs: {"data": 1}
    )
    monkeypatch.setattr(impl, "extract_common_songs", lambda setlists: ["songs"])
    stale_date = pd.Timestamp("2020-01-01")
    monkeypatch.setattr(
        impl, "extract_last_setlist", lambda songs_by_date: (["old", "older"], stale_date)
    )
    monkeypatch.setattr(impl, "extract_smart_setlist", lambda songs_by_date, max_len: ["smart"])

    songs = impl.collect_band_songs(
        "Band",
        copy_last_setlist_threshold=1,
        max_setlist_length=10,
        setlist_cache=create_null_cache(),
        force_smart_setlist=False,
    )

    assert songs == ["old", "older"]


def test_create_and_populate_playlist_uses_injected_sp(monkeypatch):
    sentinel_sp = object()
    sentinel_playlist = object()
    calls = {}

    def fake_make_spotify():
        raise AssertionError("make_spotify should not be called when sp is provided")

    def fake_find_playlist(sp, playlist_name):
        calls["playlist_name"] = playlist_name
        calls["sp"] = sp
        return sentinel_playlist

    def fake_populate(sp, playlist, songs, track_cache):
        calls["populate_args"] = {
            "sp": sp,
            "playlist": playlist,
            "songs": songs,
            "track_cache": track_cache,
        }

    monkeypatch.setattr(impl, "make_spotify", fake_make_spotify)
    monkeypatch.setattr(impl, "find_or_create_spotify_playlist", fake_find_playlist)
    monkeypatch.setattr(impl, "populate_spotify_playlist", fake_populate)

    songs = {"Band": ["a", "b"]}
    result = impl.create_and_populate_playlist(
        songs, "Playlist Name", spotify_cache=create_null_cache(), sp=sentinel_sp
    )

    assert result is sentinel_playlist
    assert calls["playlist_name"] == "Playlist Name"
    assert calls["sp"] is sentinel_sp
    assert calls["populate_args"]["songs"] == songs
    assert calls["populate_args"]["playlist"] is sentinel_playlist
    assert calls["populate_args"]["sp"] is sentinel_sp


def test_create_playlist_from_lineup_orchestrates(monkeypatch):
    monkeypatch.setattr(impl, "resolve_lineup", lambda band_names, resolvers: ["BandX"])
    monkeypatch.setattr(
        impl,
        "collect_band_songs",
        lambda band, **kwargs: ["song1", "song2"],
    )
    sentinel_playlist = object()
    captured = {}

    def fake_create_and_populate(all_songs, playlist_name, spotify_cache, sp=None):
        captured["all_songs"] = all_songs
        captured["playlist_name"] = playlist_name
        captured["spotify_cache"] = spotify_cache
        captured["sp"] = sp
        return sentinel_playlist

    monkeypatch.setattr(impl, "create_and_populate_playlist", fake_create_and_populate)

    result = impl.create_playlist_from_lineup(
        ("BandX",),
        "My Playlist",
        copy_last_setlist_threshold=5,
        max_setlist_length=10,
    )

    assert result is sentinel_playlist
    assert captured["all_songs"] == {"BandX": ["song1", "song2"]}
    assert captured["playlist_name"] == "My Playlist"
    assert captured["sp"] is None
