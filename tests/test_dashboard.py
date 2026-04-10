from app.dashboard import growing_and_slowing, period_compare, scorecard


def test_scorecard_and_growth_lists():
    videos = [
        {"video_id": "1", "view_count": 1000},
        {"video_id": "2", "view_count": 2000},
    ]
    s = scorecard(videos, {"changed": 2})
    assert s["total_views"] == 3000
    assert s["total_videos"] == 2

    changed = [
        {"title": "A", "view_diff": 100},
        {"title": "B", "view_diff": -20},
        {"title": "C", "view_diff": 30},
    ]
    g, l = growing_and_slowing(changed)
    assert g[0]["title"] == "A"
    assert l[0]["title"] == "B"


def test_period_compare():
    payload = {"rows": [["2026-01-01", 10], ["2026-01-02", 15], ["2026-01-03", 20]]}
    result = period_compare(payload)
    assert result["daily"]["current"] == 20
