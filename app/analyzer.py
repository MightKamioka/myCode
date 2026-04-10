from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "this",
    "from",
    "your",
    "have",
    "will",
    "you",
    "about",
    "into",
    "without",
    "what",
    "when",
    "where",
    "how",
    "why",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "is",
    "it",
    "be",
    "as",
    "by",
    "or",
}


@dataclass
class AnalysisResult:
    seo_score: int
    keyword_density: dict[str, float]
    suggested_tags: list[str]
    title_suggestions: list[str]
    description_suggestion: str
    retention_risk_segments: list[str]


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9']+", text.lower()) if t]


def keyword_density(tokens: Iterable[str], top_n: int = 10) -> dict[str, float]:
    tokens_list = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    if not tokens_list:
        return {}
    counts = Counter(tokens_list)
    total = sum(counts.values())
    most_common = counts.most_common(top_n)
    return {word: round((count / total) * 100, 2) for word, count in most_common}


def calculate_seo_score(title: str, description: str, tags: list[str], transcript: str) -> int:
    score = 0
    title_len = len(title)
    desc_len = len(description)

    if 45 <= title_len <= 65:
        score += 25
    elif 35 <= title_len <= 80:
        score += 15

    if 150 <= desc_len <= 300:
        score += 20
    elif 80 <= desc_len <= 400:
        score += 10

    if 8 <= len(tags) <= 20:
        score += 20
    elif 3 <= len(tags) <= 25:
        score += 10

    transcript_words = tokenize(transcript)
    if len(transcript_words) >= 300:
        score += 20
    elif len(transcript_words) >= 120:
        score += 10

    tokens = tokenize(title + " " + description + " " + transcript)
    density = keyword_density(tokens, top_n=3)
    if density and any(v >= 2.0 for v in density.values()):
        score += 15
    elif density:
        score += 8

    return max(0, min(100, score))


def suggest_titles(primary_keywords: list[str], title: str) -> list[str]:
    base = primary_keywords[:3]
    if not base:
        return [title[:60] if title else "How to Improve Your Video SEO Fast"]
    templates = [
        "{k1}: Complete Guide for 2026",
        "Top {k1} Tips That Actually Work",
        "{k1} + {k2}: What Creators Should Know",
        "Avoid These {k1} Mistakes ({k2} Edition)",
        "{k1} Strategy: Grow Faster with {k3}",
    ]
    k = base + [base[-1]] * (3 - len(base))
    suggestions = []
    for tpl in templates:
        suggestion = tpl.format(k1=k[0].title(), k2=k[1].title(), k3=k[2].title())
        suggestions.append(suggestion[:70])
    return suggestions


def suggest_description(title: str, keywords: list[str]) -> str:
    top = ", ".join(k.title() for k in keywords[:5])
    return (
        f"In this video, we break down {title or 'the strategy'} step by step. "
        f"You will learn actionable techniques for {top}. "
        "Watch until the end for a practical checklist you can apply today."
    )


def detect_retention_risk(transcript: str) -> list[str]:
    words = tokenize(transcript)
    if not words:
        return ["Intro (0:00-0:30): No transcript provided. Add a strong hook."]

    approx_segments = 5
    seg_size = max(1, math.ceil(len(words) / approx_segments))
    segments = [words[i : i + seg_size] for i in range(0, len(words), seg_size)]

    risks = []
    for idx, seg in enumerate(segments[:approx_segments]):
        unique_ratio = len(set(seg)) / max(1, len(seg))
        if unique_ratio < 0.45:
            risks.append(
                f"Segment {idx + 1}: Repetitive phrasing detected. Consider pattern interrupt."
            )
    if not risks:
        risks.append("No high-risk repetition detected. Keep pacing dynamic with visuals.")
    return risks


def analyze_video(
    title: str,
    description: str,
    tags_raw: str,
    transcript: str,
) -> AnalysisResult:
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    combined_tokens = tokenize(" ".join([title, description, transcript]))
    density = keyword_density(combined_tokens)
    primary_keywords = list(density.keys())[:5]

    return AnalysisResult(
        seo_score=calculate_seo_score(title, description, tags, transcript),
        keyword_density=density,
        suggested_tags=list(dict.fromkeys((tags + primary_keywords)))[:20],
        title_suggestions=suggest_titles(primary_keywords, title),
        description_suggestion=suggest_description(title, primary_keywords),
        retention_risk_segments=detect_retention_risk(transcript),
    )
