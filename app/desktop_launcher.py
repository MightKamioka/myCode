from __future__ import annotations

import argparse
import threading
import time
import webbrowser


def _open_browser_delayed(url: str, delay_seconds: float = 1.2) -> None:
    """Open the app URL after the server has had a moment to start."""
    time.sleep(delay_seconds)
    webbrowser.open(url)


def launch(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    """Launch the FastAPI app and optionally open the browser."""
    import uvicorn

    url = f"http://{host}:{port}"
    if open_browser:
        threading.Thread(target=_open_browser_delayed, args=(url,), daemon=True).start()
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local VidIQ-like Analyzer launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind")
    parser.add_argument("--no-browser", action="store_true", help="Disable automatic browser launch")
    args = parser.parse_args()
    launch(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
