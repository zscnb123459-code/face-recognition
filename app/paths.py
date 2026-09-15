"""Application paths and runtime identity."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FaceVault"
APP_DISPLAY_NAME = "FaceVault 人脸保险库"
APP_SUBTITLE = "Private Face Recognition System"
APP_VERSION = "1.0.0"
ORGANIZATION_NAME = "FaceVault Local"


def is_frozen() -> bool:
    """Return True when running from a PyInstaller executable."""

    return bool(getattr(sys, "frozen", False))


def application_dir() -> Path:
    """Return the directory users see as the portable application folder."""

    portable_root = os.environ.get("FACEVAULT_PORTABLE_ROOT")
    if portable_root:
        return Path(portable_root).expanduser().resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_dir() -> Path:
    """Return the PyInstaller extraction directory or the source directory."""

    return Path(getattr(sys, "_MEIPASS", application_dir())).resolve()


def resource_path(*parts: str) -> Path:
    """Resolve a bundled resource path, with a source-tree fallback."""

    bundled = bundled_dir().joinpath("resources", *parts)
    if bundled.exists():
        return bundled
    return application_dir().joinpath("resources", *parts)


def default_data_dir() -> Path:
    """Choose a portable data directory next to the executable when possible."""

    portable = application_dir() / "FaceVaultData"
    try:
        portable.mkdir(parents=True, exist_ok=True)
        return portable
    except OSError:
        fallback = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FaceVault"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
