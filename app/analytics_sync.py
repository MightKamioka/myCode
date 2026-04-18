from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _write_versioned(payload: dict, out_dir: str, prefix: str) -> Path:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snap = target / f"{prefix}_{ts}.json"
    snap.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (target / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap


def fetch_channel_analytics(analytics_client: Any, channel_id: str, days: int = 28) -> dict:
    end = date.today()
    start = end - timedelta(days=days)
    return (
        analytics_client.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost",
            dimensions="day",
            sort="day",
        )
        .execute()
    )


def fetch_search_terms(analytics_client: Any, channel_id: str, days: int = 28) -> dict:
    end = date.today()
    start = end - timedelta(days=days)
    return (
        analytics_client.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,watchTimeMinutes",
            dimensions="insightTrafficSourceDetail",
            filters="insightTrafficSourceType==YT_SEARCH",
            sort="-views",
            maxResults=200,
        )
        .execute()
    )


def fetch_audience_retention_top_videos(analytics_client: Any, channel_id: str, days: int = 28) -> dict:
    end = date.today()
    start = end - timedelta(days=days)
    return (
        analytics_client.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost",
            dimensions="video",
            sort="-averageViewPercentage",
            maxResults=50,
        )
        .execute()
    )


def fetch_top_playlists(analytics_client: Any, channel_id: str, days: int = 28) -> dict:
    end = date.today()
    start = end - timedelta(days=days)
    return (
        analytics_client.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched",
            dimensions="playlist",
            sort="-views",
            maxResults=30,
        )
        .execute()
    )


def fetch_traffic_sources(analytics_client: Any, channel_id: str, days: int = 28) -> dict:
    end = date.today()
    start = end - timedelta(days=days)
    return (
        analytics_client.reports()
        .query(
            ids=f"channel=={channel_id}",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,watchTimeMinutes",
            dimensions="insightTrafficSourceType",
            sort="-views",
            maxResults=30,
        )
        .execute()
    )


def _wrap(payload: dict) -> dict:
    return {"recorded_at": datetime.now(tz=timezone.utc).isoformat(), "payload": payload}


def save_analytics_snapshot(payload: dict, out_dir: str) -> Path:
    return _write_versioned(_wrap(payload), out_dir=out_dir, prefix="analytics")


def save_search_terms_snapshot(payload: dict, out_dir: str) -> Path:
    return _write_versioned(_wrap(payload), out_dir=out_dir, prefix="search_terms")


def save_retention_snapshot(payload: dict, out_dir: str) -> Path:
    return _write_versioned(_wrap(payload), out_dir=out_dir, prefix="retention")


def save_playlist_snapshot(payload: dict, out_dir: str) -> Path:
    return _write_versioned(_wrap(payload), out_dir=out_dir, prefix="playlist")


def save_traffic_source_snapshot(payload: dict, out_dir: str) -> Path:
    return _write_versioned(_wrap(payload), out_dir=out_dir, prefix="traffic_sources")
