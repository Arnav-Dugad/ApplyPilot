"""Desktop entry point: runs the local service and opens ApplyPilot in a native window."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.request
import webbrowser
from pathlib import Path

from .database import data_dir

TITLE = "ApplyPilot"


def _wait_until_ready(url: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1):
                return
        except OSError:
            threading.Event().wait(0.05)
    raise RuntimeError("The local ApplyPilot service did not start")


def _native_window(url: str) -> bool:
    """pywebview renders with Edge WebView2 on Windows. Returns False if it is unavailable."""
    try:
        import webview

        webview.create_window(TITLE, url, width=1360, height=880, min_size=(1100, 700), background_color="#0a0d12")
        webview.start(private_mode=False, storage_path=str(data_dir() / "webview"))
        return True
    except Exception:
        return False


def _edge_app_window(url: str, profile: Path) -> bool:
    """Chromeless Edge window; blocks until it closes because it uses its own profile directory."""
    candidates = [shutil.which("msedge")] + [
        str(Path(os.environ.get(root, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
        for root in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")
    ]
    edge = next((c for c in candidates if c and Path(c).is_file()), None)
    if not edge:
        return False
    subprocess.run([edge, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--window-size=1360,880"], check=False)
    return True


def _log_crash() -> Path:
    log = data_dir() / "logs" / "desktop-error.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(traceback.format_exc(), encoding="utf-8")
    return log


def main() -> None:
    from .server import create_server, static_dir

    if static_dir() is None:
        raise SystemExit("The ApplyPilot UI is missing. Run `npm run build` first.")
    server = create_server("127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, name="applypilot-service", daemon=True).start()
    _wait_until_ready(url)
    try:
        if not _native_window(url) and not _edge_app_window(url, data_dir() / "edge-profile"):
            webbrowser.open(url)
            print(f"ApplyPilot is running at {url}. Press Ctrl+C to quit.", flush=True)
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


def run() -> None:
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log = _log_crash()
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, f"ApplyPilot could not start.\n\nDetails were saved to:\n{log}", TITLE, 0x10)
        raise


if __name__ == "__main__":
    run()
