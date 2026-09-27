"""Bridge to desktop-only abilities (tray notifications, window placement, autostart).

The HTTP service and Autopilot call these hooks; when ApplyPilot runs without its desktop
window (development server, tests) every hook is a harmless no-op.
"""
from __future__ import annotations

import sys
from typing import Any, Callable

hooks: dict[str, Callable[..., Any]] = {}

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "ApplyPilot"


def call(name: str, *args: Any) -> Any:
    fn = hooks.get(name)
    if not fn:
        return None
    try:
        return fn(*args)
    except Exception:
        return None


def toast(title: str, body: str = "") -> None:
    call("toast", title, body)


def set_start_with_windows(enabled: bool) -> bool:
    """Adds or removes ApplyPilot from the current user's startup programs. Installed app only."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, f'"{sys.executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass
    return True


def dock_for_split(hwnd: int, fraction: float = 0.42) -> dict[str, int] | None:
    """Moves ApplyPilot to the left of the work area; returns the right-hand pane in DIPs for Edge."""
    if sys.platform != "win32" or not hwnd:
        return None
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    area = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0)  # SPI_GETWORKAREA, physical pixels
    width, height = area.right - area.left, area.bottom - area.top
    left_width = int(width * fraction)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE (leave maximized state)
    user32.SetWindowPos(hwnd, 0, area.left, area.top, left_width, height, 0x0004 | 0x0010)  # NOZORDER | NOACTIVATE
    try:
        scale = user32.GetDpiForWindow(hwnd) / 96 or 1
    except AttributeError:
        scale = 1
    return {"left": round((area.left + left_width) / scale), "top": round(area.top / scale), "width": round((width - left_width) / scale), "height": round(height / scale)}
