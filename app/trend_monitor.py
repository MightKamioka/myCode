from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import request


RULES_FILE = Path("data/monitoring_rules.json")
NOTIFY_DIR = Path("data/notifications")


@dataclass
class MonitorRule:
    rule_id: str
    rule_type: str  # keyword/category/competitor
    target: str
    frequency: str  # daily/every2/weekly
    threshold: float
    last_run_at: str | None = None


def load_rules() -> list[MonitorRule]:
    if not RULES_FILE.exists():
        return []
    data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    return [MonitorRule(**r) for r in data]


def save_rules(rules: list[MonitorRule]) -> None:
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps([asdict(r) for r in rules], ensure_ascii=False, indent=2), encoding="utf-8")


def should_run(frequency: str, last_run_at: str | None, now: datetime | None = None) -> bool:
    now = now or datetime.now(tz=timezone.utc)
    if not last_run_at:
        return True
    last = datetime.fromisoformat(last_run_at)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    hours = {"daily": 24, "every2": 48, "weekly": 24 * 7}.get(frequency, 24)
    return now - last >= timedelta(hours=hours)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def detect_keyword_trend(channel_root: Path, keyword: str, threshold: float) -> dict | None:
    data = _read_json(channel_root / "keyword_research" / "latest.json", {})
    for row in data.get("rising_keywords", []):
        if keyword.lower() in row.get("keyword", "").lower() and row.get("trend_score", 0) >= threshold:
            return {"type": "keyword", "message": f"Keyword rising: {row['keyword']} trend={row['trend_score']}"}
    return None


def detect_category_trend(channel_root: Path, category: str, threshold: float) -> dict | None:
    audit = _read_json(channel_root / "traffic_source_snapshots" / "latest.json", {})
    rows = audit.get("payload", {}).get("rows", [])
    for row in rows:
        if len(row) >= 2 and category.lower() in str(row[0]).lower() and float(row[1]) >= threshold:
            return {"type": "category", "message": f"Category/source trend: {row[0]} views={row[1]}"}
    return None


def detect_competitor_trend(competitor_analysis: dict, competitor_name: str, threshold: float) -> dict | None:
    for c in competitor_analysis.get("competitors", []):
        if competitor_name.lower() in c.get("name", "").lower() and float(c.get("growth_7d", 0)) >= threshold:
            return {"type": "competitor", "message": f"Competitor growth spike: {c['name']} 7d={c['growth_7d']}%"}
    return None


def save_notifications(alerts: list[dict]) -> Path:
    NOTIFY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {"created_at": datetime.now(tz=timezone.utc).isoformat(), "alerts": alerts}
    p = NOTIFY_DIR / f"alerts_{ts}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (NOTIFY_DIR / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_latest_notifications() -> dict:
    return _read_json(NOTIFY_DIR / "latest.json", {"alerts": []})


def maybe_send_webhook(alerts: list[dict], webhook_url: str | None) -> None:
    if not webhook_url or not alerts:
        return
    data = json.dumps({"alerts": alerts}).encode("utf-8")
    req = request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        request.urlopen(req, timeout=5)
    except Exception:
        pass
