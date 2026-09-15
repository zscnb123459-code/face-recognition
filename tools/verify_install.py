"""Validate FaceVault runtime dependencies, models and SQLite."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import PySide6

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database
from app.recognition import FaceEngine


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"OpenCV: {cv2.__version__}")
    print(f"PySide6: {PySide6.__version__}")
    print(f"NumPy: {np.__version__}")
    print(f"SQLite: {sqlite3.sqlite_version}")
    engine = FaceEngine()
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = engine.detect(blank)
    print(f"模型加载：OK；空白帧人脸数={len(faces)}")
    with tempfile.TemporaryDirectory() as temp:
        database = Database(Path(temp) / "verify.db")
        assert database.dashboard_counts()["people"] == 0
    print("SQLite 初始化：OK")
    print("FACEVAULT_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
