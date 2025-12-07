import logging
from typing import Callable, Dict, Iterable, List, Optional

from ag.hellfest import get_hellfest_lineup

FestivalResolver = Callable[[], Optional[List[str]]]
DEFAULT_FESTIVAL_RESOLVERS: Dict[str, FestivalResolver] = {
    "hellfest": get_hellfest_lineup
}


def resolve_lineup(
    band_names: Iterable[str], festival_resolvers: Dict[str, FestivalResolver]
) -> List[str]:
    lineup: List[str] = []
    for name in band_names:
        resolver = festival_resolvers.get(name.lower())
        if resolver:
            festival_lineup = resolver()
            if not festival_lineup:
                raise RuntimeError(f"Failed to get lineup for festival: {name}")
            logging.info("Resolved festival %s to %s artists", name, len(festival_lineup))
            lineup.extend(festival_lineup)
        else:
            lineup.append(name)
    return lineup
