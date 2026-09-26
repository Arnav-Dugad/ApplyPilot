"""PyInstaller entry point. Kept outside the package so `backend` imports resolve as a package."""
from backend.desktop import run

if __name__ == "__main__":
    run()
