"""Desktop entry point: runs the local service, opens the native window, and lives in the system tray."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from . import __version__, shell, updater
from .database import ROOT, data_dir

TITLE = "ApplyPilot"
MUTEX_NAME = "Local\\ApplyPilot.SingleInstance"


def _wait_until_ready(url: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=1):
                return
        except OSError:
            threading.Event().wait(0.05)
    raise RuntimeError("The local ApplyPilot service did not start")


def _instance_file() -> Path:
    return data_dir() / "instance.json"


def _already_running() -> bool:
    """Single instance: a second launch brings the running window forward instead of starting twice."""
    if sys.platform != "win32":
        return False
    import ctypes

    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() != 183:  # ERROR_ALREADY_EXISTS
        return False
    try:
        port = json.loads(_instance_file().read_text())["port"]
        request = urllib.request.Request(f"http://127.0.0.1:{port}/api/app/show", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(request, timeout=3).close()
    except Exception:
        pass
    return True


def _icon_path() -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "assets" / "applypilot.png"
    return bundled if bundled.is_file() else ROOT / "packaging" / "applypilot.png"


def _edge_app_window(url: str, profile: Path) -> bool:
    """Fallback: chromeless Edge window; blocks until it closes because it uses its own profile directory."""
    candidates = [shutil.which("msedge")] + [str(Path(os.environ.get(root, "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe") for root in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
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


class Desktop:
    """Owns the window and tray icon, and wires them into the service through shell hooks."""

    def __init__(self, url: str, minimized: bool):
        self.url = url
        self.minimized = minimized
        self.quitting = False
        self.window: Any = None
        self.tray: Any = None
        self.told_about_tray = False

    def setting(self, key: str, default: Any = None) -> Any:
        from .service import DB

        value = DB.setting(key)
        return default if value is None else value

    # --- tray -------------------------------------------------------------
    def start_tray(self) -> None:
        try:
            import pystray
            from PIL import Image
        except ImportError:
            return

        def run_autopilot(_icon: Any = None, _item: Any = None) -> None:
            from .service import AUTOPILOT

            try:
                AUTOPILOT.start("TRAY")
                self.toast("Autopilot is running", "ApplyPilot will let you know what it finds.")
            except Exception as exc:
                self.toast("Autopilot", str(exc))

        menu = pystray.Menu(
            pystray.MenuItem("Open ApplyPilot", lambda *_: self.show(), default=True),
            pystray.MenuItem("Run Autopilot now", run_autopilot),
            pystray.MenuItem("Check for updates", lambda *_: threading.Thread(target=self.check_updates, daemon=True).start()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit ApplyPilot", lambda *_: self.quit()),
        )
        self.tray = pystray.Icon("ApplyPilot", Image.open(_icon_path()), f"ApplyPilot {__version__}", menu)
        self.tray.run_detached()

    def toast(self, title: str, body: str = "") -> None:
        if self.tray is not None:
            try:
                self.tray.notify(body or " ", title)
            except Exception:
                pass

    def check_updates(self) -> None:
        result = updater.check()
        if result["status"] == "available":
            self.toast(f"ApplyPilot {result['latest']} is available", "Open ApplyPilot to see what's new.")
        elif result["status"] == "up_to_date":
            self.toast("ApplyPilot is up to date", f"You have the latest version, {__version__}.")

    # --- window -----------------------------------------------------------
    def show(self) -> None:
        if self.window is not None:
            self.window.show()
            self.window.restore()

    def hwnd(self) -> int:
        try:
            return int(self.window.native.Handle.ToInt64())
        except Exception:
            import ctypes

            return int(ctypes.windll.user32.FindWindowW(None, TITLE) or 0)

    def on_closing(self) -> bool:
        if self.quitting or not self.setting("desktop", {}).get("close_to_tray", True) or self.tray is None:
            self.quitting = True
            return True
        self.window.hide()
        if not self.told_about_tray:
            self.told_about_tray = True
            self.toast("ApplyPilot is still running", "Autopilot keeps working in the background. Right-click the tray icon to quit.")
        return False  # cancels the close; the window is only hidden

    def quit(self) -> None:
        self.quitting = True
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.window is not None:
            self.window.destroy()

    def run(self) -> bool:
        try:
            import webview
        except ImportError:
            return False
        self.window = webview.create_window(TITLE, self.url, width=1400, height=900, min_size=(1100, 700), background_color="#0a0d12", hidden=self.minimized)
        self.window.events.closing += self.on_closing
        shell.hooks.update({"toast": self.toast, "show": self.show, "dock": lambda: shell.dock_for_split(self.hwnd())})
        updater.set_quit_callback(self.quit)
        self.start_tray()
        try:
            webview.start(private_mode=False, storage_path=str(data_dir() / "webview"))
        except Exception:
            return False
        return True


def _announce_update() -> None:
    """After an update, tell the user once what version they're on now."""
    from .service import DB, notify

    last = DB.setting("last_version")
    if last and last != __version__:
        notify("UPDATE", f"Updated to ApplyPilot {__version__}", f"You were on {last}. See Settings → Updates for what's new.", "Settings")
        DB.set_setting("whats_new_pending", __version__)  # the UI celebrates and offers the release notes once
        DB.set_setting("updated_from", last)
    DB.set_setting("last_version", __version__)


def main() -> None:
    minimized = "--minimized" in sys.argv
    if _already_running():
        return
    from .server import _live_runs, create_server, static_dir
    from .service import AUTOPILOT, DB

    if static_dir() is None:
        raise SystemExit("The ApplyPilot UI is missing. Run `npm run build` first.")
    server = create_server("127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, name="applypilot-service", daemon=True).start()
    _instance_file().write_text(json.dumps({"port": server.server_port, "pid": os.getpid()}))
    _announce_update()
    AUTOPILOT.start_scheduler()
    desktop = Desktop(url, minimized)
    updater.start_background(
        auto_download=lambda: bool((DB.setting("updates") or {}).get("auto_install", True)),
        on_ready=lambda st: (desktop.toast(f"Updating to ApplyPilot {st['latest']}", "Installing in 30 seconds — open ApplyPilot to postpone."),
                             updater.schedule_install(30, lambda: bool(AUTOPILOT.running_id or _live_runs))),
    )
    _wait_until_ready(url)
    try:
        if not desktop.run() and not _edge_app_window(url, data_dir() / "edge-profile"):
            webbrowser.open(url)
            print(f"ApplyPilot is running at {url}. Press Ctrl+C to quit.", flush=True)
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        updater.install_on_quit()
        _instance_file().unlink(missing_ok=True)
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
