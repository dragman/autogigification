import logging
from typing import Any, Dict, Optional

import requests

from ag.cache import Cache
from ag.utils.rate_limit import NullRateLimiter, RateLimiter, retry_after


class SetlistFmClient:
    """Thin client around the setlist.fm search API."""

    def __init__(
        self,
        api_key: str,
        cache: Cache,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.api_key = api_key
        self.cache = cache
        self.rate_limiter = rate_limiter or NullRateLimiter()

    def get_recent_setlists(self, artist_name: str) -> Dict[str, Any]:
        cached_setlists = self.cache.get(artist_name)
        if cached_setlists is not None:
            logging.info("Using cached setlist for %s", artist_name)
            return cached_setlists

        if not self.api_key:
            raise RuntimeError("SETLIST_FM_API_KEY not configured")

        url = f"https://api.setlist.fm/rest/1.0/search/setlists?artistName={artist_name}&p=1"
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}

        with self.rate_limiter:
            response = requests.get(url, headers=headers)

        if response.status_code == 429:
            retry_after_seconds = int(response.headers.get("Retry-After", "2"))
            logging.warning(
                "Rate limited fetching setlists for %s. Retrying in %s seconds.",
                artist_name,
                retry_after_seconds,
            )
            with retry_after(retry_after_seconds, self.rate_limiter):
                response = requests.get(url, headers=headers)

        if response.status_code == 200:
            setlists = response.json()
            self.cache.set(artist_name, setlists)
            return setlists

        logging.error("Failed to fetch setlists for %s: %s", artist_name, response.text)
        return {}
