from pathlib import Path

from app.comment_research import load_shared_user, update_shared_users


def test_update_shared_users(monkeypatch, tmp_path):
    from app import comment_research as cr

    monkeypatch.setattr(cr, "SHARED_USERS_FILE", tmp_path / "shared.json")
    comments = [
        {
            "comment_id": "c1",
            "video_id": "v1",
            "author_channel_id": "u1",
            "author_name": "Alice",
            "text": "hello",
        },
        {
            "comment_id": "c2",
            "video_id": "v2",
            "author_channel_id": "u1",
            "author_name": "Alice",
            "text": "again",
        },
    ]
    update_shared_users(comments, source_channel_id="ch1")
    user = load_shared_user("u1")
    assert user["author_name"] == "Alice"
    assert len(user["comments"]) == 2
