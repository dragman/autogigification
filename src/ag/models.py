from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Playlist:
    name: str
    id: str
    url: str

    @classmethod
    def from_spotify(cls, playlist: Dict[str, Any]) -> "Playlist":
        return cls(
            name=playlist["name"],
            id=playlist["id"],
            url=playlist["external_urls"]["spotify"],
        )


@dataclass(frozen=True)
class SongMatch:
    """Represents the mapping of a setlist song to a Spotify track (or not)."""

    name: str
    spotify_id: Optional[str]
    spotify_url: Optional[str]
    status: str  # "found" | "not_found"
    strategy: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.spotify_id is not None


@dataclass(frozen=True)
class SetlistResult:
    """Details about a band's setlist and how it was derived."""

    band: str
    setlist_type: str  # "fresh" | "estimated"
    setlist_date: Optional[str]
    last_setlist_age_days: Optional[int]
    songs: List[SongMatch]

    @property
    def missing_songs(self) -> List[str]:
        return [song.name for song in self.songs if not song.found]


@dataclass(frozen=True)
class PlaylistBuildResult:
    """Composite result of building/estimating playlists."""

    setlists: List[SetlistResult]
    playlist: Optional[Playlist] = None
    created_playlist: bool = False
