from types import SimpleNamespace

from app import sherlock_scan as ss


class _Resp:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_register_and_scan(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "REGISTRY_FILE", tmp_path / "registry.json")
    monkeypatch.setattr(ss, "RESULT_DIR", tmp_path / "results")

    def fake_urlopen(req, timeout=5):
        return _Resp(200)

    monkeypatch.setattr(ss.request, "urlopen", fake_urlopen)

    ss.register_username("alice")
    assert "alice" in ss.load_registered_usernames()

    result = ss.scan_username("alice")
    assert result["found_count"] >= 1


def test_scan_all_registered(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "REGISTRY_FILE", tmp_path / "registry.json")
    monkeypatch.setattr(ss, "RESULT_DIR", tmp_path / "results")
    monkeypatch.setattr(ss.request, "urlopen", lambda req, timeout=5: _Resp(200))

    ss.register_username("a")
    ss.register_username("b")
    results = ss.scan_all_registered()
    assert len(results) == 2


def test_platforms_include_bluesky_threads():
    assert "bluesky" in ss.PLATFORMS
    assert "threads" in ss.PLATFORMS
