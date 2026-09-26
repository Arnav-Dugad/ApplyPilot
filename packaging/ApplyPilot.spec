# PyInstaller spec for the Windows desktop build. Run via packaging/build.ps1.
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "dist"), "dist"),
        (str(ROOT / "backend" / "schema.sql"), "backend"),
    ],
    hiddenimports=["backend.server", "backend.browser_runner", "pypdf", "playwright.sync_api"],
    excludes=["tkinter", "backend.tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ApplyPilot",
    icon=str(ROOT / "packaging" / "applypilot.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ApplyPilot", upx=False)
