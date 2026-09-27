"""Self-updater: checks GitHub Releases, downloads the installer with live progress, verifies it, installs, relaunches.

Safety:
- Only this repository's releases are considered, and only its "ApplyPilot-Setup-<version>.exe" asset.
- The download must match the SHA-256 digest and size GitHub publishes for that asset, or it is discarded.
- Downgrades and pre-releases are never offered.
- Updating only runs from an installed copy; portable and developer copies are told where to download instead.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .database import data_dir, now

REPO = "Arnav-Dugad/ApplyPilot"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_PATTERN = re.compile(r"^ApplyPilot-Setup-(\d+\.\d+\.\d+)\.exe$")
DOWNLOAD_HOSTS = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
USER_AGENT = f"ApplyPilot/{__version__} (self-updater)"
CHECK_EVERY_SECONDS = 6 * 3600

_lock = threading.RLock()
_state: dict[str, Any] = {"status": "idle", "current": __version__}
_quit_callback: Callable[[], None] | None = None


def parse_version(text: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    if not match:
        raise ValueError(f"Not a release version: {text}")
    return tuple(int(x) for x in match.groups())


def install_mode() -> str:
    """'installer' for the Start-menu install, 'portable' for an unzipped copy, 'dev' when running from source."""
    if not getattr(sys, "frozen", False):
        return "dev"
    installed = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ApplyPilot"
    try:
        Path(sys.executable).resolve().relative_to(installed.resolve())
        return "installer"
    except ValueError:
        return "portable"


def state() -> dict[str, Any]:
    with _lock:
        return {**_state, "current": __version__, "mode": install_mode(), "releases_page": RELEASES_PAGE}


def _set(**changes: Any) -> None:
    with _lock:
        _state.update(changes)


def set_quit_callback(callback: Callable[[], None]) -> None:
    """The desktop shell registers how to close the app so the installer can replace its files."""
    global _quit_callback
    _quit_callback = callback


def _get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def check(fetch: Callable[[str], Any] = _get_json) -> dict[str, Any]:
    """Asks GitHub for the latest release. Never raises; errors land in the state."""
    if state()["status"] in {"downloading", "verifying", "installing"}:
        return state()
    _set(status="checking", error=None)
    try:
        release = fetch(API_LATEST)
        if release.get("draft") or release.get("prerelease"):
            raise ValueError("Latest release is not a stable release")
        latest = parse_version(str(release.get("tag_name", "")))
        asset = next((a for a in release.get("assets", []) if ASSET_PATTERN.match(a.get("name", "")) and parse_version(ASSET_PATTERN.match(a["name"]).group(1)) == latest), None)
        info = {"latest": ".".join(map(str, latest)), "notes": str(release.get("body") or "")[:20_000], "published_at": release.get("published_at"), "checked_at": now(), "release_url": release.get("html_url") or RELEASES_PAGE}
        if latest <= parse_version(__version__):
            _set(status="up_to_date", **info, asset=None)
        elif not asset or not str(asset.get("digest", "")).startswith("sha256:"):
            _set(status="error", **info, asset=None, error="The new release has no verifiable installer yet. Try again in a few minutes.")
        else:
            _set(status="available", **info, asset={"name": asset["name"], "size": int(asset["size"]), "url": asset["browser_download_url"], "sha256": asset["digest"].split(":", 1)[1].lower()},
                 downloaded=0, total=int(asset["size"]), speed=0, eta=None)
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
        _set(status="error", error=f"Couldn't check for updates: {getattr(exc, 'reason', exc)}", checked_at=now())
    return state()


def _allowed_download(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in DOWNLOAD_HOSTS


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _allowed_download(newurl):
            raise ValueError(f"Refusing to download an update from {urllib.parse.urlparse(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def updates_dir() -> Path:
    path = data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(opener: urllib.request.OpenerDirector | None = None, *, background: bool = True) -> dict[str, Any]:
    current = state()
    if current["status"] == "ready":
        return current
    if current["status"] != "available" or not current.get("asset"):
        raise ValueError("No update is available to download")
    asset = current["asset"]
    if not _allowed_download(asset["url"]) or not urllib.parse.urlparse(asset["url"]).path.startswith(f"/{REPO}/releases/download/"):
        raise ValueError("Update URL is not from ApplyPilot's official releases")
    _set(status="downloading", downloaded=0, total=asset["size"], speed=0, eta=None, error=None, started_at=time.time())

    def run() -> None:
        target = updates_dir() / asset["name"]
        partial = target.with_suffix(".part")
        digest = hashlib.sha256()
        try:
            client = opener or urllib.request.build_opener(_SafeRedirects)
            request = urllib.request.Request(asset["url"], headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"})
            received, window_start, window_bytes = 0, time.time(), 0
            with client.open(request, timeout=60) as response, open(partial, "wb") as out:
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    window_bytes += len(chunk)
                    if received > asset["size"]:
                        raise ValueError("Download is larger than the published installer")
                    elapsed = time.time() - window_start
                    if elapsed >= 0.4:
                        speed = window_bytes / elapsed
                        _set(downloaded=received, speed=round(speed), eta=round((asset["size"] - received) / speed) if speed else None)
                        window_start, window_bytes = time.time(), 0
            _set(status="verifying", downloaded=received, eta=0)
            if received != asset["size"]:
                raise ValueError(f"Download incomplete ({received} of {asset['size']} bytes)")
            if digest.hexdigest() != asset["sha256"]:
                raise ValueError("Checksum mismatch — the download was discarded")
            os.replace(partial, target)
            for old in updates_dir().glob("ApplyPilot-Setup-*.exe"):
                if old != target:
                    old.unlink(missing_ok=True)
            _set(status="ready", installer=str(target), ready_at=now())
        except Exception as exc:
            partial.unlink(missing_ok=True)
            _set(status="error", error=f"Update download failed: {exc}", downloaded=0)

    if background:
        threading.Thread(target=run, name="update-download", daemon=True).start()
    else:
        run()
    return state()


def install(*, relaunch: bool = True, launcher: Callable[[list[str]], Any] | None = None) -> dict[str, Any]:
    """Runs the verified installer silently, then closes ApplyPilot so files can be replaced."""
    current = state()
    if current["status"] != "ready" or not current.get("installer") or not Path(current["installer"]).is_file():
        raise ValueError("The update isn't downloaded yet")
    if current["mode"] != "installer":
        raise ValueError("Automatic installs only work for the installed app. Download the new version from GitHub.")
    args = [current["installer"], "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", f"/RELAUNCH={1 if relaunch else 0}"]
    _set(status="installing")
    if launcher:
        launcher(args)
    else:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(args, creationflags=flags, close_fds=True)
    if _quit_callback:
        threading.Timer(1.2, _quit_callback).start()
    return state()


def schedule_install(delay: float, is_busy: Callable[[], bool]) -> None:
    """Installs automatically after a visible countdown, unless postponed or ApplyPilot is mid-task."""
    from datetime import datetime, timedelta, timezone

    _set(install_at=(datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(), postponed=False)

    def attempt() -> None:
        current = state()
        if current["status"] != "ready" or current.get("postponed"):
            return
        if is_busy():
            _set(install_at=(datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat())
            threading.Timer(60, attempt).start()
            return
        try:
            install(relaunch=True)
        except ValueError as exc:
            _set(error=str(exc))

    threading.Timer(delay, attempt).start()


def postpone() -> dict[str, Any]:
    """'Later': keep the verified installer and apply it when ApplyPilot quits."""
    _set(postponed=True, install_at=None)
    return state()


def install_on_quit() -> None:
    """Called by the desktop shell on exit: applies a postponed update without relaunching."""
    current = state()
    if current["status"] == "ready" and current.get("postponed") and current["mode"] == "installer":
        try:
            install(relaunch=False)
        except ValueError:
            pass


def start_background(auto_download: Callable[[], bool], on_ready: Callable[[dict[str, Any]], None] | None = None) -> None:
    """Checks shortly after launch and every few hours; downloads automatically when allowed."""
    def loop() -> None:
        time.sleep(8)
        while True:
            result = check()
            if result["status"] == "available" and result["mode"] == "installer" and auto_download():
                download(background=False)
                if state()["status"] == "ready" and on_ready:
                    on_ready(state())
            time.sleep(CHECK_EVERY_SECONDS)

    threading.Thread(target=loop, name="update-check", daemon=True).start()
