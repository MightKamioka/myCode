from app.analytics_sync import (
    fetch_channel_analytics,
    fetch_search_terms,
    save_analytics_snapshot,
    save_search_terms_snapshot,
)


class _Exec:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Reports:
    def __init__(self):
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return _Exec({"rows": [["x", 1]]})


class _Analytics:
    def __init__(self):
        self.r = _Reports()

    def reports(self):
        return self.r


def test_fetch_and_save_analytics(tmp_path):
    client = _Analytics()
    payload = fetch_channel_analytics(client, "UC_TEST", days=7)
    assert payload["rows"]
    path = save_analytics_snapshot(payload, out_dir=str(tmp_path / "analytics"))
    assert path.exists()


def test_fetch_and_save_search_terms(tmp_path):
    client = _Analytics()
    payload = fetch_search_terms(client, "UC_TEST", days=7)
    assert payload["rows"]
    path = save_search_terms_snapshot(payload, out_dir=str(tmp_path / "search"))
    assert path.exists()
