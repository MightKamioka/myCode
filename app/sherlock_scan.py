from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

REGISTRY_FILE = Path("data/sherlock_registry.json")
RESULT_DIR = Path("data/sherlock_results")

PLATFORMS = {
    "github": "https://github.com/{username}",
    "x": "https://x.com/{username}",
    "instagram": "https://www.instagram.com/{username}/",
    "reddit": "https://www.reddit.com/user/{username}",
    "tiktok": "https://www.tiktok.com/@{username}",
    "pinterest": "https://www.pinterest.com/{username}/",
    "twitch": "https://www.twitch.tv/{username}",
    "medium": "https://medium.com/@{username}",
    "github_gist": "https://gist.github.com/{username}",
    "bluesky": "https://bsky.app/profile/{username}",
    "threads": "https://www.threads.net/@{username}",
}


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def register_username(username: str) -> None:
    username = username.strip()
    if not username:
        return
    data = _read_json(REGISTRY_FILE, {"usernames": []})
    usernames = set(data.get("usernames", []))
    usernames.add(username)
    _write_json(REGISTRY_FILE, {"usernames": sorted(usernames)})


def load_registered_usernames() -> list[str]:
    return _read_json(REGISTRY_FILE, {"usernames": []}).get("usernames", [])


def scan_username(username: str, timeout: int = 5) -> dict[str, Any]:
    found = []
    checked = []
    for name, pattern in PLATFORMS.items():
        url = pattern.format(username=username)
        checked.append({"platform": name, "url": url})
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                if 200 <= resp.status < 300:
                    found.append({"platform": name, "url": url, "status": resp.status})
        except error.HTTPError as e:
            if e.code in (301, 302):
                found.append({"platform": name, "url": url, "status": e.code})
        except Exception:
            continue

    payload = {
        "username": username,
        "found": found,
        "checked_count": len(checked),
        "found_count": len(found),
        "scanned_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    save_scan_result(payload)
    return payload


def save_scan_result(payload: dict) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    username = payload.get("username", "unknown")
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = RESULT_DIR / f"{username}_{ts}.json"
    _write_json(p, payload)
    _write_json(RESULT_DIR / f"{username}_latest.json", payload)
    return p


def load_latest_result(username: str) -> dict:
    return _read_json(RESULT_DIR / f"{username}_latest.json", {})


def scan_all_registered() -> list[dict]:
    results = []
    for username in load_registered_usernames():
        results.append(scan_username(username))
    return results
