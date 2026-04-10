from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_stats_history(root: Path) -> list[dict]:
    d = root / "channel_stats"
    if not d.exists():
        return []
    files = sorted(d.glob("stats_*.json"))
    return [_read_json(f, {}) for f in files]


def _latest_stats(root: Path) -> dict:
    h = _load_stats_history(root)
    return h[-1] if h else {}


def _val(snapshot: dict, key: str) -> float:
    return float(snapshot.get("statistics", {}).get(key, 0))


def _period_delta(history: list[dict], days: int, key: str) -> float:
    if len(history) < 2:
        return 0.0
    now = _val(history[-1], key)
    # coarse approximation using sample count as days
    idx = max(0, len(history) - (days + 1))
    old = _val(history[idx], key)
    return now - old


def _growth_rate(history: list[dict], days: int, key: str) -> float:
    if len(history) < 2:
        return 0.0
    idx = max(0, len(history) - (days + 1))
    old = _val(history[idx], key)
    if old <= 0:
        return 0.0
    return ((_val(history[-1], key) - old) / old) * 100


def _avg_daily_views(history: list[dict], days: int = 30) -> float:
    delta = _period_delta(history, days, "viewCount")
    return delta / days if days else 0.0


def _top_growing_videos(root: Path, limit: int = 5) -> list[dict]:
    diff = _read_json(root / "performance_diffs" / "latest.json", {"changed": []})
    changed = diff.get("changed", [])
    changed = sorted(changed, key=lambda x: x.get("view_diff", 0), reverse=True)
    return changed[:limit]


def build_competitor_analysis(channel_root: Path, monitored_roots: list[tuple[str, Path]]) -> dict[str, Any]:
    own_hist = _load_stats_history(channel_root)
    own_latest = _latest_stats(channel_root)

    comparisons = []
    for title, root in monitored_roots:
        hist = _load_stats_history(root)
        latest = _latest_stats(root)
        comparisons.append(
            {
                "name": title,
                "views": _val(latest, "viewCount"),
                "subscribers": _val(latest, "subscriberCount"),
                "video_count": _val(latest, "videoCount"),
                "compare_30d_views": _period_delta(hist, 30, "viewCount"),
                "compare_60d_views": _period_delta(hist, 60, "viewCount"),
                "compare_12m_views": _period_delta(hist, 365, "viewCount"),
                "growth_7d": _growth_rate(hist, 7, "viewCount"),
                "growth_14d": _growth_rate(hist, 14, "viewCount"),
                "growth_28d": _growth_rate(hist, 28, "viewCount"),
                "avg_daily_views": _avg_daily_views(hist, 30),
                "top_growing_videos": _top_growing_videos(root),
            }
        )

    return {
        "own": {
            "views": _val(own_latest, "viewCount"),
            "subscribers": _val(own_latest, "subscriberCount"),
            "video_count": _val(own_latest, "videoCount"),
            "growth_7d": _growth_rate(own_hist, 7, "viewCount"),
            "growth_14d": _growth_rate(own_hist, 14, "viewCount"),
            "growth_28d": _growth_rate(own_hist, 28, "viewCount"),
            "avg_daily_views": _avg_daily_views(own_hist, 30),
        },
        "competitors": comparisons,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
