from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from starlette.middleware.sessions import SessionMiddleware

from app.analytics_sync import (
    fetch_audience_retention_top_videos,
    fetch_channel_analytics,
    fetch_search_terms,
    fetch_top_playlists,
    fetch_traffic_sources,
    save_analytics_snapshot,
    save_playlist_snapshot,
    save_retention_snapshot,
    save_search_terms_snapshot,
    save_traffic_source_snapshot,
)
from app.analyzer import analyze_video
from app.channel_audit import build_channel_audit
from app.competitor_analysis import build_competitor_analysis
from app.dashboard import build_dashboard
from app.keyword_research import load_latest_keyword_research, run_keyword_research
from app.youtube_sync import run_full_sync, should_sync_on_login
from app.comment_research import (
    fetch_comments_for_video,
    load_latest_channel_comments,
    load_shared_user,
    load_shared_users_index,
    post_reply,
    save_channel_comments,
    update_shared_users,
)
from app.sherlock_scan import (
    load_latest_result as load_latest_sherlock_result,
    load_registered_usernames,
    register_username,
    scan_all_registered,
    scan_username,
)
from app.trend_monitor import (
    MonitorRule,
    detect_category_trend,
    detect_competitor_trend,
    detect_keyword_trend,
    load_latest_notifications,
    load_rules,
    maybe_send_webhook,
    save_notifications,
    save_rules,
    should_run,
)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secret.json")
TOKEN_FILE = Path("data/token.json")
CHANNEL_INDEX_FILE = Path("data/channels/index.json")
MONITOR_INDEX_FILE = Path("data/monitored/index.json")
SYNC_INTERVAL_MINUTES = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))

app = FastAPI(title="Local VidIQ-like Analyzer")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("APP_SESSION_SECRET", "dev-secret-change-me"))
templates = Jinja2Templates(directory="templates")

_scheduler_task: asyncio.Task | None = None


def _read_json(path: Path, default: dict | list):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _channel_root(channel_id: str) -> Path:
    return Path("data/channels") / channel_id


def _monitor_root(channel_id: str) -> Path:
    return Path("data/monitored") / channel_id


def _channel_meta_path(channel_id: str) -> Path:
    return _channel_root(channel_id) / "sync_meta.json"


def _monitor_meta_path(channel_id: str) -> Path:
    return _monitor_root(channel_id) / "sync_meta.json"


def _read_channel_meta(channel_id: str) -> dict:
    return _read_json(_channel_meta_path(channel_id), {})


def _write_channel_meta(channel_id: str, payload: dict) -> None:
    _write_json(_channel_meta_path(channel_id), payload)


def _read_monitor_meta(channel_id: str) -> dict:
    return _read_json(_monitor_meta_path(channel_id), {})


def _write_monitor_meta(channel_id: str, payload: dict) -> None:
    _write_json(_monitor_meta_path(channel_id), payload)


def _read_channel_index() -> list[dict]:
    return _read_json(CHANNEL_INDEX_FILE, [])


def _read_monitor_index() -> list[dict]:
    return _read_json(MONITOR_INDEX_FILE, [])


def _upsert_index(index_file: Path, channel_id: str, channel_title: str) -> None:
    index = _read_json(index_file, [])
    now = datetime.now(tz=timezone.utc).isoformat()
    updated = False
    for ch in index:
        if ch.get("channel_id") == channel_id:
            ch["channel_title"] = channel_title
            ch["updated_at"] = now
            updated = True
            break
    if not updated:
        index.append({"channel_id": channel_id, "channel_title": channel_title, "updated_at": now})
    _write_json(index_file, index)


def _save_sync_result(channel_id: str, channel_title: str, export_path: Path, diff_path: Path, diff_summary: dict) -> None:
    meta = _read_channel_meta(channel_id)
    meta.update(
        {
            "channel_id": channel_id,
            "channel_title": channel_title,
            "last_full_sync_at": datetime.now(tz=timezone.utc).isoformat(),
            "last_export": str(export_path),
            "last_diff_report": str(diff_path),
            "last_diff_summary": diff_summary,
        }
    )
    _write_channel_meta(channel_id, meta)
    _upsert_index(CHANNEL_INDEX_FILE, channel_id, channel_title)


def _save_monitor_sync_result(channel_id: str, channel_title: str, export_path: Path, diff_path: Path, diff_summary: dict) -> None:
    meta = _read_monitor_meta(channel_id)
    meta.update(
        {
            "channel_id": channel_id,
            "channel_title": channel_title,
            "last_full_sync_at": datetime.now(tz=timezone.utc).isoformat(),
            "last_export": str(export_path),
            "last_diff_report": str(diff_path),
            "last_diff_summary": diff_summary,
        }
    )
    _write_monitor_meta(channel_id, meta)
    _upsert_index(MONITOR_INDEX_FILE, channel_id, channel_title)


def _get_credentials() -> Credentials:
    if not TOKEN_FILE.exists():
        raise HTTPException(status_code=401, detail="YouTube未連携です。先にログインしてください。")
    data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return Credentials.from_authorized_user_info(data, SCOPES)


def _build_clients(credentials: Credentials):
    youtube = build("youtube", "v3", credentials=credentials)
    analytics = build("youtubeAnalytics", "v2", credentials=credentials)
    return youtube, analytics


def _get_my_channel(youtube_client) -> tuple[str, str]:
    res = youtube_client.channels().list(part="snippet", mine=True, maxResults=1).execute()
    items = res.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="チャンネル情報が取得できませんでした。")
    item = items[0]
    return item.get("id", "unknown"), item.get("snippet", {}).get("title", "Unknown Channel")


def _get_channel_by_id(youtube_client, channel_id: str) -> tuple[str, str]:
    res = youtube_client.channels().list(part="snippet", id=channel_id, maxResults=1).execute()
    items = res.get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail=f"指定UIDのチャンネルが見つかりません: {channel_id}")
    item = items[0]
    return item.get("id", channel_id), item.get("snippet", {}).get("title", "Unknown Channel")


def _sync_channel(youtube_client, channel_id: str, channel_title: str) -> None:
    root = _channel_root(channel_id)
    export_path, diff_path, diff = run_full_sync(
        youtube_client,
        exports_dir=str(root / "video_exports"),
        diffs_dir=str(root / "performance_diffs"),
        latest_records_path=str(root / "video_exports" / "latest.json"),
    )
    _save_sync_result(channel_id, channel_title, export_path, diff_path, diff.get("summary", {}))
    _save_channel_stats(root, _fetch_channel_stats(youtube_client, mine=True))


def _sync_channel_analytics(analytics_client, channel_id: str) -> tuple[Path, Path]:
    root = _channel_root(channel_id)
    analytics_payload = fetch_channel_analytics(analytics_client, channel_id=channel_id)
    search_payload = fetch_search_terms(analytics_client, channel_id=channel_id)
    retention_payload = fetch_audience_retention_top_videos(analytics_client, channel_id=channel_id)
    playlist_payload = fetch_top_playlists(analytics_client, channel_id=channel_id)
    traffic_payload = fetch_traffic_sources(analytics_client, channel_id=channel_id)

    analytics_path = save_analytics_snapshot(analytics_payload, out_dir=str(root / "analytics_snapshots"))
    search_terms_path = save_search_terms_snapshot(search_payload, out_dir=str(root / "search_terms_snapshots"))
    save_retention_snapshot(retention_payload, out_dir=str(root / "retention_snapshots"))
    save_playlist_snapshot(playlist_payload, out_dir=str(root / "playlist_snapshots"))
    save_traffic_source_snapshot(traffic_payload, out_dir=str(root / "traffic_source_snapshots"))
    return analytics_path, search_terms_path




def _fetch_channel_stats(youtube_client, channel_id: str | None = None, mine: bool = False) -> dict:
    req = youtube_client.channels().list(part="snippet,statistics", maxResults=1, mine=True) if mine else youtube_client.channels().list(part="snippet,statistics", id=channel_id, maxResults=1)
    res = req.execute()
    items = res.get("items", [])
    if not items:
        return {}
    it = items[0]
    return {
        "channel_id": it.get("id"),
        "title": it.get("snippet", {}).get("title"),
        "statistics": it.get("statistics", {}),
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _save_channel_stats(root: Path, stats: dict) -> None:
    if not stats:
        return
    d = root / "channel_stats"
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = d / f"stats_{ts}.json"
    p.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "latest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_monitored_channel(youtube_client, channel_id: str, channel_title: str) -> None:
    root = _monitor_root(channel_id)
    export_path, diff_path, diff = run_full_sync(
        youtube_client,
        exports_dir=str(root / "video_exports"),
        diffs_dir=str(root / "performance_diffs"),
        latest_records_path=str(root / "video_exports" / "latest.json"),
        channel_id=channel_id,
    )
    _save_monitor_sync_result(channel_id, channel_title, export_path, diff_path, diff.get("summary", {}))
    _save_channel_stats(root, _fetch_channel_stats(youtube_client, channel_id=channel_id))


def _collect_monitor_summaries() -> list[dict]:
    summaries: list[dict] = []
    for ch in _read_monitor_index():
        cid = ch.get("channel_id")
        if not cid:
            continue
        meta = _read_monitor_meta(cid)
        summaries.append({"channel_id": cid, "channel_title": ch.get("channel_title"), "last_diff_summary": meta.get("last_diff_summary")})
    return summaries


def _periodic_sync_once() -> None:
    if not TOKEN_FILE.exists():
        return
    credentials = _get_credentials()
    youtube, analytics = _build_clients(credentials)
    for ch in _read_channel_index():
        cid = ch.get("channel_id")
        title = ch.get("channel_title", "Unknown")
        if not cid:
            continue
        meta = _read_channel_meta(cid)
        if should_sync_on_login(meta.get("last_full_sync_at")):
            _sync_channel(youtube, cid, title)
            _sync_channel_analytics(analytics, cid)
    for ch in _read_monitor_index():
        cid = ch.get("channel_id")
        title = ch.get("channel_title", "Unknown")
        if cid:
            _sync_monitored_channel(youtube, cid, title)




def _run_monitoring_rules(active_channel_id: str | None = None) -> None:
    channel_id = active_channel_id
    if not channel_id:
        channels = _read_channel_index()
        channel_id = channels[0].get("channel_id") if channels else None
    if not channel_id:
        return

    channel_root = _channel_root(channel_id)
    monitored_roots = [(m.get("channel_title", "Unknown"), _monitor_root(m.get("channel_id"))) for m in _read_monitor_index() if m.get("channel_id")]
    comp = build_competitor_analysis(channel_root, monitored_roots)

    rules = load_rules()
    alerts: list[dict] = []
    now = datetime.now(tz=timezone.utc)
    for r in rules:
        if not should_run(r.frequency, r.last_run_at, now=now):
            continue
        alert = None
        if r.rule_type == "keyword":
            alert = detect_keyword_trend(channel_root, r.target, r.threshold)
        elif r.rule_type == "category":
            alert = detect_category_trend(channel_root, r.target, r.threshold)
        elif r.rule_type == "competitor":
            alert = detect_competitor_trend(comp, r.target, r.threshold)

        r.last_run_at = now.isoformat()
        if alert:
            alert["rule_id"] = r.rule_id
            alert["target"] = r.target
            alerts.append(alert)

    save_rules(rules)
    if alerts:
        save_notifications(alerts)
        maybe_send_webhook(alerts, os.getenv("TREND_WEBHOOK_URL"))


async def _periodic_sync_loop() -> None:
    while True:
        try:
            _periodic_sync_once()
            _run_monitoring_rules()
        except Exception:
            pass
        await asyncio.sleep(SYNC_INTERVAL_MINUTES * 60)


@app.on_event("startup")
async def _startup_event():
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_periodic_sync_loop())


@app.on_event("shutdown")
async def _shutdown_event():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    channels = _read_channel_index()
    active_channel_id = request.session.get("active_channel_id")
    if not active_channel_id and channels:
        active_channel_id = channels[0].get("channel_id")
        request.session["active_channel_id"] = active_channel_id
    active_meta = _read_channel_meta(active_channel_id) if active_channel_id else {}
    dashboard = build_dashboard(_channel_root(active_channel_id)) if active_channel_id else {}
    audit = build_channel_audit(_channel_root(active_channel_id)) if active_channel_id else {}
    keyword_research = load_latest_keyword_research(_channel_root(active_channel_id)) if active_channel_id else {}
    monitored_roots = [(m.get("channel_title", "Unknown"), _monitor_root(m.get("channel_id"))) for m in _read_monitor_index() if m.get("channel_id")]
    competitor_analysis = build_competitor_analysis(_channel_root(active_channel_id), monitored_roots) if active_channel_id else {}
    notifications = load_latest_notifications()
    comments_latest = load_latest_channel_comments(_channel_root(active_channel_id)) if active_channel_id else []
    focused_user_id = request.session.get("focused_user_id")
    focused_user = load_shared_user(focused_user_id) if focused_user_id else {}
    sherlock_users = load_registered_usernames()
    sherlock_latest = load_latest_sherlock_result(sherlock_users[0]) if sherlock_users else {}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "result": None,
            "youtube_connected": TOKEN_FILE.exists(),
            "channels": channels,
            "active_channel_id": active_channel_id,
            "active_channel_title": active_meta.get("channel_title"),
            "last_export": active_meta.get("last_export"),
            "last_diff_report": active_meta.get("last_diff_report"),
            "last_diff_summary": active_meta.get("last_diff_summary"),
            "monitored_channels": _collect_monitor_summaries(),
            "dashboard": dashboard,
            "channel_audit": audit,
            "keyword_research": keyword_research,
            "competitor_analysis": competitor_analysis,
            "notifications": notifications.get("alerts", []),
            "monitor_rules": [r.__dict__ for r in load_rules()],
            "comments_latest": comments_latest[:100],
            "shared_users": load_shared_users_index()[:100],
            "focused_user_id": focused_user_id,
            "focused_user": focused_user,
            "sherlock_users": sherlock_users,
            "sherlock_latest": sherlock_latest,
        },
    )


@app.get("/channel/select/{channel_id}")
async def select_channel(request: Request, channel_id: str):
    request.session["active_channel_id"] = channel_id
    return RedirectResponse(url="/", status_code=303)


@app.post("/monitor/register")
async def register_monitor(channel_uid: str = Form(...)):
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    channel_id, channel_title = _get_channel_by_id(youtube, channel_uid.strip())
    _upsert_index(MONITOR_INDEX_FILE, channel_id, channel_title)
    return RedirectResponse(url="/", status_code=303)


@app.post("/monitor/sync")
async def sync_monitors():
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    for ch in _read_monitor_index():
        cid = ch.get("channel_id")
        if cid:
            _sync_monitored_channel(youtube, cid, ch.get("channel_title", "Unknown"))
    return RedirectResponse(url="/", status_code=303)


@app.post("/analytics/sync")
async def analytics_sync(request: Request):
    credentials = _get_credentials()
    youtube, analytics = _build_clients(credentials)
    channel_id, channel_title = _get_my_channel(youtube)
    request.session["active_channel_id"] = channel_id
    _sync_channel_analytics(analytics, channel_id)
    _upsert_index(CHANNEL_INDEX_FILE, channel_id, channel_title)
    return RedirectResponse(url="/", status_code=303)


@app.post("/keywords/research")
async def keywords_research(request: Request):
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    channel_id, channel_title = _get_my_channel(youtube)
    request.session["active_channel_id"] = channel_id
    _upsert_index(CHANNEL_INDEX_FILE, channel_id, channel_title)

    meta = _read_channel_meta(channel_id)
    channel_scale = float(meta.get("last_diff_summary", {}).get("total_views", 0) or 0)
    run_keyword_research(youtube, _channel_root(channel_id), channel_scale=channel_scale)
    return RedirectResponse(url="/", status_code=303)


@app.post("/monitoring/rules")
async def add_monitor_rule(rule_type: str = Form(...), target: str = Form(...), frequency: str = Form("daily"), threshold: float = Form(10.0)):
    rules = load_rules()
    rid = f"rule_{len(rules)+1}_{int(datetime.now(tz=timezone.utc).timestamp())}"
    rules.append(MonitorRule(rule_id=rid, rule_type=rule_type, target=target, frequency=frequency, threshold=threshold))
    save_rules(rules)
    return RedirectResponse(url="/", status_code=303)


@app.post("/monitoring/scan")
async def run_monitor_scan(request: Request):
    _run_monitoring_rules(request.session.get("active_channel_id"))
    return RedirectResponse(url="/", status_code=303)


@app.post("/comments/sync")
async def sync_comments(request: Request):
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    channel_id = request.session.get("active_channel_id")
    if not channel_id:
        cid, _ = _get_my_channel(youtube)
        channel_id = cid

    root = _channel_root(channel_id)
    latest_videos = _read_json(root / "video_exports" / "latest.json", {"videos": []}).get("videos", [])
    comments: list[dict] = []
    for v in latest_videos[:20]:
        vid = v.get("video_id")
        if not vid:
            continue
        try:
            comments.extend(fetch_comments_for_video(youtube, vid, max_pages=2))
        except Exception:
            continue

    save_channel_comments(root, comments)
    update_shared_users(comments, source_channel_id=channel_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/comments/focus")
async def focus_user(request: Request, user_id: str = Form(...)):
    request.session["focused_user_id"] = user_id
    return RedirectResponse(url="/", status_code=303)


@app.post("/comments/reply")
async def reply_comment(parent_comment_id: str = Form(...), reply_text: str = Form(...)):
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    post_reply(youtube, parent_comment_id, reply_text)
    return RedirectResponse(url="/", status_code=303)


@app.post("/sherlock/register")
async def sherlock_register(username: str = Form(...)):
    register_username(username)
    return RedirectResponse(url="/", status_code=303)


@app.post("/sherlock/scan")
async def sherlock_scan(username: str = Form(...)):
    scan_username(username.strip())
    return RedirectResponse(url="/", status_code=303)


@app.post("/sherlock/scan_all")
async def sherlock_scan_all():
    scan_all_registered()
    return RedirectResponse(url="/", status_code=303)


@app.post("/self-test")
async def self_test():
    credentials = _get_credentials()
    youtube, analytics = _build_clients(credentials)

    ch = youtube.channels().list(part="snippet,statistics", mine=True, maxResults=1).execute()
    channel_ok = len(ch.get("items", [])) > 0

    channel_id = ch.get("items", [{}])[0].get("id", "") if channel_ok else ""
    analytics_ok = False
    if channel_id:
        try:
            analytics.reports().query(
                ids=f"channel=={channel_id}",
                startDate=(datetime.now(tz=timezone.utc).date()).isoformat(),
                endDate=(datetime.now(tz=timezone.utc).date()).isoformat(),
                metrics="views",
            ).execute()
            analytics_ok = True
        except Exception:
            analytics_ok = False

    return JSONResponse({
        "channel_api_ok": channel_ok,
        "analytics_api_ok": analytics_ok,
        "channel_id": channel_id,
    })


@app.get("/youtube/connect")
async def youtube_connect(request: Request):
    if not Path(CLIENT_SECRET_FILE).exists():
        raise HTTPException(status_code=500, detail="client_secret.json が見つかりません。")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=str(request.url_for("oauth_callback")),
    )
    authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="select_account consent")
    request.session["oauth_state"] = state
    return RedirectResponse(authorization_url)


@app.get("/oauth2callback", name="oauth_callback")
async def oauth_callback(request: Request):
    state = request.session.get("oauth_state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=str(request.url_for("oauth_callback")),
    )
    flow.fetch_token(authorization_response=str(request.url))
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")

    youtube, analytics = _build_clients(flow.credentials)
    channel_id, channel_title = _get_my_channel(youtube)
    request.session["active_channel_id"] = channel_id
    _upsert_index(CHANNEL_INDEX_FILE, channel_id, channel_title)
    meta = _read_channel_meta(channel_id)
    if should_sync_on_login(meta.get("last_full_sync_at")):
        _sync_channel(youtube, channel_id, channel_title)
        _sync_channel_analytics(analytics, channel_id)
    return RedirectResponse(url="/")


@app.post("/youtube/sync")
async def youtube_sync(request: Request):
    credentials = _get_credentials()
    youtube, _ = _build_clients(credentials)
    channel_id, channel_title = _get_my_channel(youtube)
    request.session["active_channel_id"] = channel_id
    _sync_channel(youtube, channel_id, channel_title)
    return RedirectResponse(url="/", status_code=303)


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    transcript: str = Form(""),
):
    result = analyze_video(title=title, description=description, tags_raw=tags, transcript=transcript)
    channels = _read_channel_index()
    active_channel_id = request.session.get("active_channel_id")
    active_meta = _read_channel_meta(active_channel_id) if active_channel_id else {}
    dashboard = build_dashboard(_channel_root(active_channel_id)) if active_channel_id else {}
    audit = build_channel_audit(_channel_root(active_channel_id)) if active_channel_id else {}
    keyword_research = load_latest_keyword_research(_channel_root(active_channel_id)) if active_channel_id else {}
    monitored_roots = [(m.get("channel_title", "Unknown"), _monitor_root(m.get("channel_id"))) for m in _read_monitor_index() if m.get("channel_id")]
    competitor_analysis = build_competitor_analysis(_channel_root(active_channel_id), monitored_roots) if active_channel_id else {}
    notifications = load_latest_notifications()
    comments_latest = load_latest_channel_comments(_channel_root(active_channel_id)) if active_channel_id else []
    focused_user_id = request.session.get("focused_user_id")
    focused_user = load_shared_user(focused_user_id) if focused_user_id else {}
    sherlock_users = load_registered_usernames()
    sherlock_latest = load_latest_sherlock_result(sherlock_users[0]) if sherlock_users else {}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "result": result,
            "youtube_connected": TOKEN_FILE.exists(),
            "channels": channels,
            "active_channel_id": active_channel_id,
            "active_channel_title": active_meta.get("channel_title"),
            "last_export": active_meta.get("last_export"),
            "last_diff_report": active_meta.get("last_diff_report"),
            "last_diff_summary": active_meta.get("last_diff_summary"),
            "monitored_channels": _collect_monitor_summaries(),
            "dashboard": dashboard,
            "channel_audit": audit,
            "keyword_research": keyword_research,
            "competitor_analysis": competitor_analysis,
            "notifications": notifications.get("alerts", []),
            "monitor_rules": [r.__dict__ for r in load_rules()],
            "comments_latest": comments_latest[:100],
            "shared_users": load_shared_users_index()[:100],
            "focused_user_id": focused_user_id,
            "focused_user": focused_user,
            "sherlock_users": sherlock_users,
            "sherlock_latest": sherlock_latest,
            "input": {"title": title, "description": description, "tags": tags, "transcript": transcript},
        },
    )
