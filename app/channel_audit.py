from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("payload", {})


def _sum_col(rows: list[list[Any]], idx: int) -> float:
    return sum(float(r[idx]) for r in rows if len(r) > idx)


def build_channel_audit(channel_root: Path) -> dict[str, Any]:
    analytics = _read_payload(channel_root / "analytics_snapshots" / "latest.json")
    retention = _read_payload(channel_root / "retention_snapshots" / "latest.json")
    playlists = _read_payload(channel_root / "playlist_snapshots" / "latest.json")
    traffic = _read_payload(channel_root / "traffic_source_snapshots" / "latest.json")

    day_rows = analytics.get("rows", [])
    total_views = _sum_col(day_rows, 1)
    total_watch_min = _sum_col(day_rows, 2)
    avg_view_duration = (_sum_col(day_rows, 3) / len(day_rows)) if day_rows else 0.0
    subs_gained = _sum_col(day_rows, 4)
    subs_lost = _sum_col(day_rows, 5)
    subs_net = subs_gained - subs_lost

    # VPH approximation from tracked window
    hours = max(1, len(day_rows) * 24)
    vph = total_views / hours

    retention_rows = retention.get("rows", [])
    # rows: [video, views, avgViewDuration, avgViewPercentage, likes, comments, shares, subsGained, subsLost]
    total_interactions = _sum_col(retention_rows, 4) + _sum_col(retention_rows, 5) + _sum_col(retention_rows, 6)
    engagement_rate = (total_interactions / total_views * 100) if total_views > 0 else 0.0

    top_retention = sorted(retention_rows, key=lambda r: float(r[3]) if len(r) > 3 else 0, reverse=True)[:5]
    top_playlists = playlists.get("rows", [])[:5]
    traffic_sources = traffic.get("rows", [])[:5]

    return {
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "vph": round(vph, 2),
        "engagement_rate": round(engagement_rate, 2),
        "subscribers_net": int(subs_net),
        "total_watch_minutes": round(total_watch_min, 2),
        "average_view_duration": round(avg_view_duration, 2),
        "top_retention_videos": top_retention,
        "top_playlists": top_playlists,
        "traffic_sources": traffic_sources,
    }
