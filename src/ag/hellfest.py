import re
from typing import List, Optional
import urllib

import requests
from bs4 import BeautifulSoup

HELLFEST_URL = "https://www.hellfest.fr/line-up"


def get_hellfest_lineup() -> Optional[List[str]]:
    response = requests.get(HELLFEST_URL)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        lineup = []
        for artist_tag in soup.select("a.artist-block"):
            href = artist_tag["href"]
            # Extract the artist name from the href, which is the last part of the URL
            artist_name_encoded = href.split("/")[-2]
            artist_name = urllib.parse.unquote(artist_name_encoded)
            # Remove any non-alphanumeric characters except spaces
            artist_name_clean = re.sub(r"[^\w]", " ", artist_name).strip()
            lineup.append(artist_name_clean)
        return lineup
    return None
