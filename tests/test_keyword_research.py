from app.keyword_research import build_opportunities, compute_keyword_trends, related_keywords


def test_compute_trends_and_related():
    snaps = [
        {"rows": [["python tutorial", 10], ["fastapi", 5]]},
        {"rows": [["python tutorial", 20], ["fastapi", 4], ["seo tips", 8]]},
    ]
    trends = compute_keyword_trends(snaps)
    assert trends["python tutorial"]["growth"] == 10
    rel = related_keywords(list(trends.keys()))
    assert "python" in rel


def test_build_opportunities():
    trends = {
        "python tutorial": {"latest": 20, "growth_ratio": 100},
        "fastapi": {"latest": 4, "growth_ratio": -20},
    }
    comp = {"python tutorial": 40, "fastapi": 80}
    opp = build_opportunities(trends, comp, channel_scale=500)
    assert opp[0].keyword == "python tutorial"
    assert opp[0].target_fit in {"high", "medium", "low"}
