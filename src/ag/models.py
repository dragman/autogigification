from dataclasses import dataclass
from typing import Any, Dict


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
