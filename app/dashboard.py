from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path, default: dict | list):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_latest_video_snapshot(channel_root: Path) -> dict:
    return _read_json(channel_root / "video_exports" / "latest.json", {"videos": []})


def load_latest_diff_snapshot(channel_root: Path) -> dict:
    return _read_json(channel_root / "performance_diffs" / "latest.json", {"changed": [], "summary": {}})


def load_latest_analytics_snapshot(channel_root: Path) -> dict:
    snap = _read_json(channel_root / "analytics_snapshots" / "latest.json", {"payload": {}})
    return snap.get("payload", {})


def _to_dt(text: str) -> datetime:
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def latest_videos(videos: list[dict], limit: int = 10) -> list[dict]:
    return sorted(videos, key=lambda v: _to_dt(v.get("published_at", "")), reverse=True)[:limit]


def growing_and_slowing(diff_changed: list[dict], limit: int = 5) -> tuple[list[dict], list[dict]]:
    growing = sorted(diff_changed, key=lambda r: r.get("view_diff", 0), reverse=True)
    slowing = sorted(diff_changed, key=lambda r: r.get("view_diff", 0))
    return growing[:limit], [r for r in slowing[:limit] if r.get("view_diff", 0) < 0]


def scorecard(videos: list[dict], diff_summary: dict) -> dict[str, Any]:
    total_views = sum(int(v.get("view_count", 0)) for v in videos)
    total_videos = len(videos)
    avg_views = int(total_views / total_videos) if total_videos else 0
    momentum = diff_summary.get("changed", 0)
    return {
        "total_videos": total_videos,
        "total_views": total_views,
        "avg_views": avg_views,
        "momentum_items": momentum,
        "health": "good" if avg_views >= 1000 else "normal" if avg_views >= 200 else "low",
    }


def period_compare(analytics_payload: dict) -> dict[str, dict[str, int]]:
    rows = analytics_payload.get("rows", [])
    # rows: [day, views, estMinutes, avgDur, subsGained, subsLost]
    daily_views = [int(r[1]) for r in rows if len(r) > 1]
    if not daily_views:
        return {"daily": {"current": 0, "previous": 0}, "weekly": {"current": 0, "previous": 0}, "monthly": {"current": 0, "previous": 0}}

    def compare(window: int) -> dict[str, int]:
        current = sum(daily_views[-window:])
        previous = sum(daily_views[-(2 * window) : -window]) if len(daily_views) > window else 0
        return {"current": current, "previous": previous}

    return {
        "daily": compare(1),
        "weekly": compare(7),
        "monthly": compare(28),
    }


def build_dashboard(channel_root: Path) -> dict[str, Any]:
    latest = load_latest_video_snapshot(channel_root)
    diff = load_latest_diff_snapshot(channel_root)
    analytics = load_latest_analytics_snapshot(channel_root)

    videos = latest.get("videos", [])
    changed = diff.get("changed", [])
    growing, slowing = growing_and_slowing(changed)

    return {
        "latest_videos": latest_videos(videos),
        "growing_videos": growing,
        "slowing_videos": slowing,
        "scorecard": scorecard(videos, diff.get("summary", {})),
        "live_like": {
            "last_changed_count": len(changed),
            "last_added": diff.get("summary", {}).get("added", 0),
            "last_removed": diff.get("summary", {}).get("removed", 0),
        },
        "period_compare": period_compare(analytics),
    }
