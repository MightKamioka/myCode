from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class VideoRecord:
    video_id: str
    title: str
    description: str
    published_at: str
    privacy_status: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
    tags: list[str] = field(default_factory=list)


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _style_features(title: str, description: str) -> dict[str, Any]:
    title_alpha = [c for c in title if c.isalpha()]
    title_upper = [c for c in title_alpha if c.isupper()]
    upper_ratio = (len(title_upper) / len(title_alpha)) if title_alpha else 0.0
    exclamations = title.count("!") + description.count("!")
    return {
        "title_length": len(title),
        "description_length": len(description),
        "title_upper_ratio": round(upper_ratio, 3),
        "exclamation_count": exclamations,
    }


def fetch_my_video_ids(youtube_client: Any, page_limit: int = 20) -> list[str]:
    ids: list[str] = []
    next_page_token: str | None = None

    for _ in range(page_limit):
        response = (
            youtube_client.search()
            .list(
                part="id",
                forMine=True,
                type="video",
                maxResults=50,
                pageToken=next_page_token,
            )
            .execute()
        )
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                ids.append(video_id)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return list(dict.fromkeys(ids))


def fetch_channel_video_ids(youtube_client: Any, channel_id: str, page_limit: int = 20) -> list[str]:
    ids: list[str] = []
    next_page_token: str | None = None

    for _ in range(page_limit):
        response = (
            youtube_client.search()
            .list(
                part="id",
                channelId=channel_id,
                type="video",
                order="date",
                maxResults=50,
                pageToken=next_page_token,
            )
            .execute()
        )
        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                ids.append(video_id)

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return list(dict.fromkeys(ids))


def fetch_video_details(youtube_client: Any, video_ids: list[str]) -> list[VideoRecord]:
    records: list[VideoRecord] = []
    for batch in _chunks(video_ids, 50):
        response = (
            youtube_client.videos()
            .list(
                part="snippet,status,statistics,contentDetails",
                id=",".join(batch),
                maxResults=50,
            )
            .execute()
        )

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            status = item.get("status", {})
            content = item.get("contentDetails", {})
            records.append(
                VideoRecord(
                    video_id=item.get("id", ""),
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    published_at=snippet.get("publishedAt", ""),
                    privacy_status=status.get("privacyStatus", "unknown"),
                    view_count=int(stats.get("viewCount", 0)),
                    like_count=int(stats.get("likeCount", 0)),
                    comment_count=int(stats.get("commentCount", 0)),
                    duration=content.get("duration", ""),
                    tags=snippet.get("tags", []),
                )
            )

    return records


def export_records(records: list[VideoRecord], out_dir: str = "data/video_exports") -> Path:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    payload = {
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "count": len(records),
        "videos": [asdict(r) for r in records],
    }

    snapshot_path = target_dir / f"videos_{ts}.json"
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = target_dir / "latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return snapshot_path


def load_latest_records(path: str = "data/video_exports/latest.json") -> list[VideoRecord]:
    latest_path = Path(path)
    if not latest_path.exists():
        return []

    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    records: list[VideoRecord] = []
    for item in payload.get("videos", []):
        normalized = {
            "video_id": item.get("video_id", ""),
            "title": item.get("title", ""),
            "description": item.get("description", ""),
            "published_at": item.get("published_at", ""),
            "privacy_status": item.get("privacy_status", "unknown"),
            "view_count": int(item.get("view_count", 0)),
            "like_count": int(item.get("like_count", 0)),
            "comment_count": int(item.get("comment_count", 0)),
            "duration": item.get("duration", ""),
            "tags": item.get("tags", []),
        }
        records.append(VideoRecord(**normalized))
    return records


def diff_records(previous: list[VideoRecord], current: list[VideoRecord]) -> dict[str, Any]:
    prev_map = {r.video_id: r for r in previous}
    cur_map = {r.video_id: r for r in current}

    added = [asdict(cur_map[k]) for k in sorted(set(cur_map) - set(prev_map))]
    removed = [asdict(prev_map[k]) for k in sorted(set(prev_map) - set(cur_map))]

    changed = []
    for video_id in sorted(set(cur_map) & set(prev_map)):
        before = prev_map[video_id]
        after = cur_map[video_id]
        view_diff = after.view_count - before.view_count
        like_diff = after.like_count - before.like_count
        comment_diff = after.comment_count - before.comment_count
        privacy_changed = before.privacy_status != after.privacy_status
        title_changed = before.title != after.title
        description_changed = before.description != after.description

        before_tags = set(before.tags)
        after_tags = set(after.tags)
        tags_added = sorted(after_tags - before_tags)
        tags_removed = sorted(before_tags - after_tags)

        before_style = _style_features(before.title, before.description)
        after_style = _style_features(after.title, after.description)
        style_changed = before_style != after_style

        if (
            view_diff
            or like_diff
            or comment_diff
            or privacy_changed
            or title_changed
            or description_changed
            or tags_added
            or tags_removed
            or style_changed
        ):
            changed.append(
                {
                    "video_id": video_id,
                    "title": after.title,
                    "privacy_status_before": before.privacy_status,
                    "privacy_status_after": after.privacy_status,
                    "view_diff": view_diff,
                    "like_diff": like_diff,
                    "comment_diff": comment_diff,
                    "title_changed": title_changed,
                    "description_changed": description_changed,
                    "tags_added": tags_added,
                    "tags_removed": tags_removed,
                    "style_before": before_style,
                    "style_after": after_style,
                }
            )

    return {
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "total_views": sum(r.view_count for r in current),
            "total_likes": sum(r.like_count for r in current),
            "total_comments": sum(r.comment_count for r in current),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def save_diff_report(diff: dict[str, Any], out_dir: str = "data/performance_diffs") -> Path:
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    payload = {
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        **diff,
    }

    report_path = target_dir / f"diff_{ts}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = target_dir / "latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def should_sync_on_login(last_synced_at: str | None, now: datetime | None = None) -> bool:
    if not last_synced_at:
        return True

    current = now or datetime.now(tz=timezone.utc)
    previous = datetime.fromisoformat(last_synced_at)
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)

    return current - previous >= timedelta(hours=12)


def run_full_sync(
    youtube_client: Any,
    exports_dir: str = "data/video_exports",
    diffs_dir: str = "data/performance_diffs",
    latest_records_path: str | None = None,
    channel_id: str | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    latest_path = latest_records_path or str(Path(exports_dir) / "latest.json")
    previous = load_latest_records(latest_path)
    if channel_id:
        video_ids = fetch_channel_video_ids(youtube_client, channel_id=channel_id)
    else:
        video_ids = fetch_my_video_ids(youtube_client)

    current = fetch_video_details(youtube_client, video_ids)
    export_path = export_records(current, out_dir=exports_dir)

    diff = diff_records(previous, current)
    diff_path = save_diff_report(diff, out_dir=diffs_dir)
    return export_path, diff_path, diff
