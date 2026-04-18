from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class KeywordOpportunity:
    keyword: str
    volume_score: float
    competition_score: float
    trend_score: float
    opportunity_score: float
    target_fit: str


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_search_term_snapshots(channel_root: Path) -> list[dict]:
    folder = channel_root / "search_terms_snapshots"
    if not folder.exists():
        return []
    files = sorted([p for p in folder.glob("search_terms_*.json")])
    snapshots = []
    for f in files[-14:]:
        payload = _read_json(f, {})
        snapshots.append(payload.get("payload", {}))
    return snapshots


def _extract_term_views(snapshot_payload: dict) -> dict[str, float]:
    rows = snapshot_payload.get("rows", [])
    # [term, views, watchTimeMinutes]
    out: dict[str, float] = {}
    for r in rows:
        if len(r) >= 2 and r[0]:
            out[str(r[0]).lower()] = float(r[1])
    return out


def related_keywords(seed_terms: list[str]) -> list[str]:
    tokens = []
    for term in seed_terms:
        tokens.extend([t for t in term.split() if len(t) > 2])
    common = Counter(tokens).most_common(15)
    return [w for w, _ in common]


def compute_keyword_trends(snapshots: list[dict]) -> dict[str, dict[str, float]]:
    if not snapshots:
        return {}
    latest = _extract_term_views(snapshots[-1])
    previous = _extract_term_views(snapshots[-2]) if len(snapshots) > 1 else {}

    trends = {}
    for k, latest_v in latest.items():
        prev_v = previous.get(k, 0.0)
        growth = latest_v - prev_v
        growth_ratio = (growth / prev_v * 100.0) if prev_v > 0 else (100.0 if latest_v > 0 else 0.0)
        trends[k] = {"latest": latest_v, "previous": prev_v, "growth": growth, "growth_ratio": growth_ratio}
    return trends


def estimate_competition(youtube_client: Any, keyword: str) -> float:
    response = (
        youtube_client.search()
        .list(part="id", q=keyword, type="video", maxResults=1)
        .execute()
    )
    total = float(response.get("pageInfo", {}).get("totalResults", 0))
    # normalize to 0-100 logarithmic-ish
    if total <= 0:
        return 0.0
    return min(100.0, (total ** 0.5))


def _target_fit(opportunity: float, channel_scale: float) -> str:
    if channel_scale < 1000 and opportunity >= 55:
        return "high"
    if channel_scale < 10000 and opportunity >= 45:
        return "medium"
    if opportunity >= 35:
        return "medium"
    return "low"


def build_opportunities(
    trends: dict[str, dict[str, float]],
    competition_map: dict[str, float],
    channel_scale: float,
) -> list[KeywordOpportunity]:
    items: list[KeywordOpportunity] = []
    for keyword, t in trends.items():
        volume = min(100.0, t["latest"])
        competition = competition_map.get(keyword, 50.0)
        trend = max(-100.0, min(100.0, t["growth_ratio"]))
        opportunity = (volume * 0.5) + ((100 - competition) * 0.3) + ((trend + 100) / 2 * 0.2)
        fit = _target_fit(opportunity, channel_scale)
        items.append(
            KeywordOpportunity(
                keyword=keyword,
                volume_score=round(volume, 2),
                competition_score=round(competition, 2),
                trend_score=round(trend, 2),
                opportunity_score=round(opportunity, 2),
                target_fit=fit,
            )
        )
    return sorted(items, key=lambda x: x.opportunity_score, reverse=True)


def save_keyword_research(channel_root: Path, payload: dict) -> Path:
    out = channel_root / "keyword_research"
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    wrapped = {"recorded_at": datetime.now(tz=timezone.utc).isoformat(), **payload}
    p = out / f"keywords_{ts}.json"
    p.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "latest.json").write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run_keyword_research(youtube_client: Any, channel_root: Path, channel_scale: float) -> dict:
    snapshots = load_search_term_snapshots(channel_root)
    trends = compute_keyword_trends(snapshots)
    terms = list(trends.keys())[:30]

    comp = {}
    for term in terms:
        try:
            comp[term] = estimate_competition(youtube_client, term)
        except Exception:
            comp[term] = 50.0

    opps = build_opportunities(trends, comp, channel_scale=channel_scale)
    rising = sorted(opps, key=lambda x: x.trend_score, reverse=True)[:10]
    related = related_keywords([o.keyword for o in opps[:20]])

    payload = {
        "top_opportunities": [asdict(x) for x in opps[:20]],
        "rising_keywords": [asdict(x) for x in rising],
        "related_keywords": related,
        "trend_table": trends,
    }
    save_keyword_research(channel_root, payload)
    return payload


def load_latest_keyword_research(channel_root: Path) -> dict:
    return _read_json(channel_root / "keyword_research" / "latest.json", {})
