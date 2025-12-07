import pandas as pd

from ag.services.setlist_selection import extract_smart_setlist


def test_extract_smart_setlist_handles_empty():
    assert extract_smart_setlist([], 5) == []


def test_extract_smart_setlist_handles_tiny_dataset():
    songs = [("Song A", pd.Timestamp("2024-01-01"))]
    result = extract_smart_setlist(songs, 5)
    assert result[0] == "Song A"
    assert len(result) == 1
