import sys
import types

from app import desktop_launcher


def test_open_browser_delayed_uses_webbrowser(monkeypatch):
    opened = []

    monkeypatch.setattr(desktop_launcher.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(desktop_launcher.webbrowser, "open", lambda url: opened.append(url))

    desktop_launcher._open_browser_delayed("http://127.0.0.1:8000")

    assert opened == ["http://127.0.0.1:8000"]


def test_launch_runs_uvicorn_with_expected_target(monkeypatch):
    called = {}

    monkeypatch.setattr(desktop_launcher.threading, "Thread", lambda *args, **kwargs: type("T", (), {"start": lambda self: None})())

    def fake_run(target, host, port, reload):
        called["target"] = target
        called["host"] = host
        called["port"] = port
        called["reload"] = reload

    monkeypatch.setitem(sys.modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    desktop_launcher.launch(host="127.0.0.1", port=8010, open_browser=False)

    assert called == {
        "target": "app.main:app",
        "host": "127.0.0.1",
        "port": 8010,
        "reload": False,
    }
