import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union


class Cache(ABC):
    @abstractmethod
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return cached value or default."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store value under key."""

    @abstractmethod
    def persist(self) -> None:
        """Flush any pending changes."""

    @abstractmethod
    def __contains__(self, key: str) -> bool:
        """Return True if key exists."""

    def as_dict(self) -> Dict[str, Any]:
        """Expose raw cache data when needed."""
        return {}


class NullCache(Cache):
    """Cache implementation that discards everything."""

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return default

    def set(self, key: str, value: Any) -> None:
        return None

    def persist(self) -> None:
        return None

    def __contains__(self, key: str) -> bool:
        return False


class MemoryCache(Cache):
    """In-memory cache that never persists to disk."""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def persist(self) -> None:
        return None

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)


class FileCache(Cache):
    """JSON file backed cache with immediate persistence."""

    def __init__(self, cache_file: Union[str, Path], auto_persist: bool = True):
        self.cache_path = self._resolve_repo_file(cache_file)
        self.auto_persist = auto_persist
        self._data: Dict[str, Any] = self._load()

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        if self.auto_persist:
            self.persist()

    def persist(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as file:
            json.dump(self._data, file, indent=4)
        logging.info("Saved cache to %s", self.cache_path)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def _load(self) -> Dict[str, Any]:
        if self.cache_path.exists():
            with open(self.cache_path, "r") as file:
                return json.load(file)
        return {}

    @staticmethod
    def _resolve_repo_file(cache_file: Union[str, Path]) -> Path:
        cache_path = Path(cache_file)
        if not cache_path.is_absolute():
            cache_path = Path(__file__).parent.parent / cache_path
        logging.info("Using cache file %s", cache_path)
        return cache_path


def create_cache(cache_target: Optional[Union[str, Path]]) -> Cache:
    """Factory for cache instances.

    Passing None or an empty string will return an in-memory cache.
    """
    if cache_target is None:
        return MemoryCache()

    cache_name = str(cache_target).strip().lower()
    if cache_name in {"", "none", "null", "memory"}:
        return MemoryCache()

    return FileCache(cache_target)


def create_null_cache() -> Cache:
    # For legacy callers: return a no-op cache.
    return NullCache()
