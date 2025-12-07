import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CacheConfig:
    """File locations for caches."""

    setlist_cache: Optional[str]
    spotify_track_cache: Optional[str]


@dataclass(frozen=True)
class SetlistFmConfig:
    """Credentials/configuration for setlist.fm."""

    api_key: str


@dataclass(frozen=True)
class SpotifyConfig:
    """Credentials/configuration for Spotify."""

    client_id: str
    client_secret: str
    redirect_uri: Optional[str]
    username: Optional[str]
    refresh_token: Optional[str]
    scopes: str = "playlist-modify-public"
    token_cache_path: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    """Aggregated configuration passed to service constructors."""

    setlist_fm: SetlistFmConfig
    spotify: SpotifyConfig
    caches: CacheConfig


def load_app_config(*, require_spotify_user: bool = True) -> AppConfig:
    """Load configuration from environment variables."""

    setlist_api_key = os.environ.get("SETLIST_FM_API_KEY")
    if not setlist_api_key:
        raise RuntimeError("SETLIST_FM_API_KEY must be set")

    spotify_client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    spotify_client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    spotify_redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")
    spotify_username = os.environ.get("SPOTIFY_USERNAME")
    spotify_refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    missing_required = [
        name
        for name, value in {
            "SPOTIFY_CLIENT_ID": spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": spotify_client_secret,
        }.items()
        if not value
    ]
    if missing_required:
        raise RuntimeError(f"Missing Spotify config: {', '.join(missing_required)}")

    if require_spotify_user:
        missing_user = [
            name
            for name, value in {
                "SPOTIFY_REDIRECT_URI": spotify_redirect_uri,
                "SPOTIFY_USERNAME": spotify_username,
                "SPOTIFY_REFRESH_TOKEN": spotify_refresh_token,
            }.items()
            if not value
        ]
        if missing_user:
            raise RuntimeError(f"Missing Spotify user config: {', '.join(missing_user)}")

    caches = CacheConfig(
        setlist_cache=os.environ.get("SETLIST_CACHE", "setlist_cache.json"),
        spotify_track_cache=os.environ.get("SPOTIFY_TRACK_CACHE", "spotify_cache.json"),
    )

    setlist_cfg = SetlistFmConfig(api_key=setlist_api_key)
    spotify_cfg = SpotifyConfig(
        client_id=spotify_client_id,
        client_secret=spotify_client_secret,
        redirect_uri=spotify_redirect_uri,
        username=spotify_username,
        refresh_token=spotify_refresh_token,
        scopes=os.environ.get("SPOTIFY_SCOPES", "playlist-modify-public"),
        token_cache_path=os.environ.get("SPOTIFY_CACHE_PATH", "/tmp/spotify_token_cache"),
    )

    return AppConfig(setlist_fm=setlist_cfg, spotify=spotify_cfg, caches=caches)
