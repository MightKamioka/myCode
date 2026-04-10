from datetime import datetime, timezone

from app.youtube_sync import (
    VideoRecord,
    diff_records,
    export_records,
    fetch_channel_video_ids,
    fetch_my_video_ids,
    fetch_video_details,
    run_full_sync,
    should_sync_on_login,
)


class _Exec:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _SearchEndpoint:
    def __init__(self, responses):
        self.responses = responses
        self.idx = 0

    def list(self, **kwargs):
        payload = self.responses[self.idx]
        self.idx += 1
        return _Exec(payload)


class _VideosEndpoint:
    def __init__(self, response):
        self.response = response

    def list(self, **kwargs):
        return _Exec(self.response)


class _MockYoutube:
    def __init__(self):
        self._search = _SearchEndpoint(
            [
                {
                    "items": [{"id": {"videoId": "v1"}}, {"id": {"videoId": "v2"}}],
                    "nextPageToken": "next",
                },
                {"items": [{"id": {"videoId": "v3"}}]},
            ]
        )
        self._videos = _VideosEndpoint(
            {
                "items": [
                    {
                        "id": "v1",
                        "snippet": {
                            "title": "A",
                            "description": "D",
                            "publishedAt": "2026-01-01",
                            "tags": ["x", "y"],
                        },
                        "status": {"privacyStatus": "private"},
                        "statistics": {"viewCount": "1", "likeCount": "2", "commentCount": "3"},
                        "contentDetails": {"duration": "PT1M"},
                    }
                ]
            }
        )

    def search(self):
        return self._search

    def videos(self):
        return self._videos


def test_fetch_my_video_ids_collects_pages():
    youtube = _MockYoutube()
    ids = fetch_my_video_ids(youtube)
    assert ids == ["v1", "v2", "v3"]


def test_fetch_channel_video_ids_collects_pages():
    youtube = _MockYoutube()
    ids = fetch_channel_video_ids(youtube, channel_id="UC_TEST")
    assert ids == ["v1", "v2", "v3"]


def test_fetch_video_details_and_export(tmp_path):
    youtube = _MockYoutube()
    records = fetch_video_details(youtube, ["v1"])
    assert records[0].privacy_status == "private"
    assert records[0].tags == ["x", "y"]

    export_path = export_records(records, out_dir=str(tmp_path))
    assert export_path.exists()
    assert (tmp_path / "latest.json").exists()


def test_diff_records_catches_text_and_tag_changes():
    previous = [
        VideoRecord("v1", "OLD TITLE", "desc", "2026", "public", 10, 2, 1, "PT1M", tags=["a", "b"]),
    ]
    current = [
        VideoRecord(
            "v1",
            "New title!",
            "desc updated!",
            "2026",
            "public",
            15,
            3,
            1,
            "PT1M",
            tags=["b", "c"],
        ),
    ]

    diff = diff_records(previous, current)
    row = diff["changed"][0]
    assert row["title_changed"] is True
    assert row["description_changed"] is True
    assert row["tags_added"] == ["c"]
    assert row["tags_removed"] == ["a"]
    assert row["style_before"] != row["style_after"]


def test_should_sync_on_login_12h_rule():
    assert should_sync_on_login(None)

    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert not should_sync_on_login("2026-01-01T03:00:00+00:00", now=now)
    assert should_sync_on_login("2025-12-31T23:00:00+00:00", now=now)


def test_run_full_sync_writes_to_channel_scoped_dirs(tmp_path):
    youtube = _MockYoutube()
    exports_dir = tmp_path / "channels" / "c1" / "video_exports"
    diffs_dir = tmp_path / "channels" / "c1" / "performance_diffs"
    export_path, diff_path, diff = run_full_sync(
        youtube,
        exports_dir=str(exports_dir),
        diffs_dir=str(diffs_dir),
        latest_records_path=str(exports_dir / "latest.json"),
        channel_id="UC_TEST",
    )

    assert export_path.exists()
    assert diff_path.exists()
    assert (exports_dir / "latest.json").exists()
    assert (diffs_dir / "latest.json").exists()
    assert "summary" in diff
