import json
from datetime import datetime, timezone
from pathlib import Path

from app.trend_monitor import detect_category_trend, detect_keyword_trend, should_run


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_should_run_by_frequency():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    assert should_run("daily", None, now=now)
    assert not should_run("daily", "2026-01-09T12:00:00+00:00", now=now)
    assert should_run("weekly", "2025-12-31T00:00:00+00:00", now=now)


def test_detect_keyword_and_category(tmp_path):
    root = tmp_path / "channels" / "c1"
    _write(root / "keyword_research" / "latest.json", {"rising_keywords": [{"keyword": "python", "trend_score": 50}]})
    _write(root / "traffic_source_snapshots" / "latest.json", {"payload": {"rows": [["YT_SEARCH", 1000, 200]]}})

    kw = detect_keyword_trend(root, "python", threshold=20)
    cat = detect_category_trend(root, "search", threshold=500)
    assert kw is not None
    assert cat is not None
