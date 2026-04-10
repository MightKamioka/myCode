from app.analyzer import analyze_video, tokenize


def test_tokenize_basic():
    assert tokenize("Hello, World!") == ["hello", "world"]


def test_analyze_video_has_score_and_suggestions():
    result = analyze_video(
        title="YouTube SEO for Beginners",
        description="Learn practical methods to improve your ranking and click-through rate.",
        tags_raw="youtube seo,content strategy,thumbnail",
        transcript=" ".join(["youtube", "seo", "strategy", "audience"] * 120),
    )
    assert 0 <= result.seo_score <= 100
    assert len(result.title_suggestions) >= 1
    assert len(result.suggested_tags) >= 3
