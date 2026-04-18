from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHARED_USERS_FILE = Path("data/comment_users_shared.json")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_comments_for_video(youtube_client: Any, video_id: str, max_pages: int = 3) -> list[dict]:
    out: list[dict] = []
    token = None
    for _ in range(max_pages):
        resp = (
            youtube_client.commentThreads()
            .list(
                part="snippet,replies",
                videoId=video_id,
                textFormat="plainText",
                maxResults=100,
                pageToken=token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            out.append(
                {
                    "comment_id": item.get("snippet", {}).get("topLevelComment", {}).get("id"),
                    "video_id": video_id,
                    "author_channel_id": top.get("authorChannelId", {}).get("value", "unknown"),
                    "author_name": top.get("authorDisplayName", "unknown"),
                    "text": top.get("textDisplay", ""),
                    "like_count": top.get("likeCount", 0),
                    "published_at": top.get("publishedAt", ""),
                }
            )
        token = resp.get("nextPageToken")
        if not token:
            break
    return out


def save_channel_comments(channel_root: Path, comments: list[dict]) -> Path:
    d = channel_root / "comments"
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"captured_at": datetime.now(tz=timezone.utc).isoformat(), "comments": comments}
    p = d / f"comments_{ts}.json"
    _write_json(p, payload)
    _write_json(d / "latest.json", payload)
    return p


def load_latest_channel_comments(channel_root: Path) -> list[dict]:
    data = _read_json(channel_root / "comments" / "latest.json", {"comments": []})
    return data.get("comments", [])


def update_shared_users(comments: list[dict], source_channel_id: str) -> None:
    shared = _read_json(SHARED_USERS_FILE, {"users": {}})
    users = shared.setdefault("users", {})
    for c in comments:
        uid = c.get("author_channel_id", "unknown")
        rec = users.setdefault(uid, {"author_name": c.get("author_name", "unknown"), "comments": []})
        rec["author_name"] = c.get("author_name", rec.get("author_name", "unknown"))
        rec["comments"].append({**c, "source_channel_id": source_channel_id})
        # de-dup by comment_id
        seen = {}
        for row in rec["comments"]:
            seen[row.get("comment_id")] = row
        rec["comments"] = list(seen.values())
    _write_json(SHARED_USERS_FILE, shared)


def load_shared_user(user_id: str) -> dict:
    shared = _read_json(SHARED_USERS_FILE, {"users": {}})
    return shared.get("users", {}).get(user_id, {"author_name": "", "comments": []})


def load_shared_users_index() -> list[dict]:
    shared = _read_json(SHARED_USERS_FILE, {"users": {}})
    out = []
    for uid, data in shared.get("users", {}).items():
        out.append({"user_id": uid, "author_name": data.get("author_name"), "comment_count": len(data.get("comments", []))})
    return sorted(out, key=lambda x: x["comment_count"], reverse=True)


def post_reply(youtube_client: Any, parent_comment_id: str, text: str) -> dict:
    return (
        youtube_client.comments()
        .insert(
            part="snippet",
            body={
                "snippet": {
                    "parentId": parent_comment_id,
                    "textOriginal": text,
                }
            },
        )
        .execute()
    )
