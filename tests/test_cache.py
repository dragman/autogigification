from ag.cache import FileCache, MemoryCache, create_cache


def test_memory_cache_roundtrip():
    cache = MemoryCache()
    assert cache.get("missing") is None
    cache.set("foo", "bar")
    assert "foo" in cache
    assert cache.get("foo") == "bar"


def test_create_cache_uses_memory_for_none_and_memory_label(tmp_path, monkeypatch):
    assert isinstance(create_cache(None), MemoryCache)
    assert isinstance(create_cache(""), MemoryCache)
    assert isinstance(create_cache("memory"), MemoryCache)
    assert isinstance(create_cache("none"), MemoryCache)

    # Non-empty path should yield FileCache
    path = tmp_path / "cache.json"
    cache = create_cache(str(path))
    assert isinstance(cache, FileCache)


def test_file_cache_persists(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache = FileCache(cache_path)
    cache.set("foo", "bar")
    cache.persist()

    cache2 = FileCache(cache_path)
    assert cache2.get("foo") == "bar"
