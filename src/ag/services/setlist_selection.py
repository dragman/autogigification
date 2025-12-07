import logging
import pandas as pd
from typing import List, Tuple


def derive_song_features(
    songs_by_date: List[Tuple[str, pd.Timestamp]], decay_rate: float
) -> pd.DataFrame:
    if not songs_by_date:
        return pd.DataFrame()

    names, dates = zip(*songs_by_date)
    df = pd.DataFrame({"name": names, "date": dates})

    days_since_played = (pd.Timestamp.now() - df["date"]).dt.days  # type: ignore
    df["weight"] = decay_rate ** (days_since_played / 30)

    df["position"] = df.groupby("date").cumcount() + 1
    df["setlist_size"] = df.groupby("date")["name"].transform("count")

    df["is_first"] = df["position"] == 1
    df["is_last"] = df["position"] == df["setlist_size"]

    return df


def extract_common_songs(setlists) -> List[Tuple[str, pd.Timestamp]]:
    songs_played_by_date = []
    events = setlists["setlist"]
    for event in events:
        event_date = event["eventDate"]
        url = event["url"]
        for set_i, set_ in enumerate(event["sets"]["set"]):
            songs = set_["song"]
            for song in songs:
                song_name = song.get("name")
                song_is_tape = song.get("tape", False)

                if not song_name:
                    logging.warning(
                        f"No song name in set {set_i} on {event_date=} {url=}"
                    )
                    continue

                if song_is_tape:
                    logging.info(f"{song_name} is a tape, ignoring")
                    continue

                songs_played_by_date.append(
                    (song_name, pd.to_datetime(event_date, dayfirst=True))
                )

            if not songs:
                logging.warning(f"No songs in set {set_i} on {event_date=} {url=}")
                continue

    return songs_played_by_date


def extract_last_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]],
) -> Tuple[List[str], pd.Timestamp]:
    songs, dates = zip(*songs_by_date)
    song_series = pd.Series(songs, index=dates)
    song_series = song_series.sort_index(ascending=False)
    last_date: pd.Timestamp = song_series.index[0]  # type: ignore
    last_setlist = song_series.loc[last_date]

    if len(last_setlist) < 5:
        logging.info(f"Less than 5 songs played on {last_date}")

    return list(last_setlist), last_date


def extract_smart_setlist(
    songs_by_date: List[Tuple[str, pd.Timestamp]], setlist_length: int
) -> List[str]:
    df = derive_song_features(songs_by_date, decay_rate=0.9)
    if df.empty:
        logging.warning("No song data available to build smart setlist")
        return []

    df["normalised_position"] = df["position"] / df["setlist_size"]

    position_bins = [0, 0.2, 0.8, 1]
    position_labels = ["Start", "Middle", "End"]
    df["position_bin"] = pd.cut(
        df["normalised_position"], bins=position_bins, labels=position_labels
    )

    weighted_position_freq = (
        df.groupby(["position_bin", "name"], observed=True)["weight"]
        .sum()
        .unstack(fill_value=0)
    )

    overall_weight = df.groupby("name")["weight"].sum().sort_values(ascending=False)

    def _first_available(weights: pd.Series, exclude: set) -> str:
        for name in weights.index:
            if name not in exclude:
                return name
        return weights.index[0]

    first_candidates = df.loc[df["is_first"]].groupby("name")["weight"].sum()
    most_likely_first = (
        first_candidates.idxmax()
        if not first_candidates.empty
        else _first_available(overall_weight, set())
    )

    last_candidates = df.loc[df["is_last"]].groupby("name")["weight"].sum()
    most_likely_last = (
        last_candidates.idxmax()
        if not last_candidates.empty
        else _first_available(overall_weight, {most_likely_first})
    )

    all_songs = {most_likely_first, most_likely_last}
    setlist = [most_likely_first]

    for i in range(2, setlist_length):
        remaining = [song for song in overall_weight.index if song not in all_songs]
        if not remaining:
            break

        current_bin = position_labels[i // setlist_length]
        if current_bin in weighted_position_freq.index:
            remaining_weights = (
                weighted_position_freq.loc[current_bin].reindex(remaining, fill_value=0)
            )
            most_likely_song = remaining_weights.idxmax()
        else:
            logging.info("Position bin %s missing, falling back to overall weights", current_bin)
            most_likely_song = remaining[0]

        setlist.append(most_likely_song)
        all_songs.add(most_likely_song)

    if most_likely_last not in all_songs:
        setlist.append(most_likely_last)

    return setlist  # type: ignore


def should_use_smart_setlist(last_setlist_age_days: int, threshold_days: int) -> bool:
    return last_setlist_age_days > threshold_days
