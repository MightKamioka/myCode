import json
from pathlib import Path

from app.competitor_analysis import build_competitor_analysis


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_competitor_analysis_basic(tmp_path):
    own = tmp_path / "channels" / "own"
    comp = tmp_path / "monitored" / "c1"

    _write(own / "channel_stats" / "stats_1.json", {"statistics": {"viewCount": 1000, "subscriberCount": 100, "videoCount": 10}})
    _write(own / "channel_stats" / "stats_2.json", {"statistics": {"viewCount": 1300, "subscriberCount": 110, "videoCount": 11}})

    _write(comp / "channel_stats" / "stats_1.json", {"statistics": {"viewCount": 2000, "subscriberCount": 300, "videoCount": 20}})
    _write(comp / "channel_stats" / "stats_2.json", {"statistics": {"viewCount": 2600, "subscriberCount": 320, "videoCount": 21}})
    _write(comp / "performance_diffs" / "latest.json", {"changed": [{"title": "v", "view_diff": 500}]})

    result = build_competitor_analysis(own, [("CompA", comp)])
    assert result["own"]["views"] == 1300
    assert result["competitors"][0]["views"] == 2600
    assert result["competitors"][0]["top_growing_videos"][0]["view_diff"] == 500
