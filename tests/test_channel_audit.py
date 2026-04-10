import json
from pathlib import Path

from app.channel_audit import build_channel_audit


def _write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_channel_audit(tmp_path):
    root = tmp_path / "channels" / "c1"
    _write(root / "analytics_snapshots" / "latest.json", {"payload": {"rows": [["2026-01-01", 240, 120, 30, 10, 2]]}})
    _write(root / "retention_snapshots" / "latest.json", {"payload": {"rows": [["vid1", 100, 20, 55.0, 5, 2, 1, 1, 0]]}})
    _write(root / "playlist_snapshots" / "latest.json", {"payload": {"rows": [["PL1", 1000, 500]]}})
    _write(root / "traffic_source_snapshots" / "latest.json", {"payload": {"rows": [["YT_SEARCH", 500, 200]]}})

    audit = build_channel_audit(root)
    assert audit["vph"] == 10.0
    assert audit["subscribers_net"] == 8
    assert len(audit["top_retention_videos"]) == 1
