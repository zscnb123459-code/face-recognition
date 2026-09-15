"""Portable JSON settings with validation and safe defaults."""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.config import (
    DEFAULT_HISTORY_COOLDOWN_SECONDS,
    DEFAULT_MIN_FACE_SIZE,
    DEFAULT_RECOGNITION_THRESHOLD,
    DEFAULT_STABLE_FRAMES,
    SUPPORTED_RESOLUTIONS,
)
from app.paths import application_dir, default_data_dir
from app.utils.logging_setup import get_logger

logger = get_logger("settings")


DEFAULT_SETTINGS: dict[str, Any] = {
    "camera_index": 0,
    "resolution": "1280x720",
    "fps_limit": 30,
    "recognition_threshold": DEFAULT_RECOGNITION_THRESHOLD,
    "stable_frames": DEFAULT_STABLE_FRAMES,
    "history_cooldown_seconds": DEFAULT_HISTORY_COOLDOWN_SECONDS,
    "min_face_size": DEFAULT_MIN_FACE_SIZE,
    "camera_auto_start": False,
    "theme": "dark",
    "data_directory": "",
}


class SettingsService:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or (application_dir() / "FaceVault.config.json")
        self._lock = threading.RLock()
        self._values = self._load()

    def _load(self) -> dict[str, Any]:
        values = deepcopy(DEFAULT_SETTINGS)
        if self.config_path.exists():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    values.update(raw)
            except (OSError, json.JSONDecodeError):
                logger.exception("设置文件损坏，已使用安全默认值")
        return self._validate(values)

    @staticmethod
    def _validate(values: dict[str, Any]) -> dict[str, Any]:
        clean = deepcopy(DEFAULT_SETTINGS)
        try:
            clean["camera_index"] = max(0, min(32, int(values.get("camera_index", 0))))
        except (TypeError, ValueError):
            pass
        resolution = str(values.get("resolution", clean["resolution"]))
        clean["resolution"] = (
            resolution if resolution in SUPPORTED_RESOLUTIONS else clean["resolution"]
        )
        try:
            clean["fps_limit"] = max(5, min(60, int(values.get("fps_limit", 30))))
        except (TypeError, ValueError):
            pass
        try:
            threshold = float(
                values.get("recognition_threshold", clean["recognition_threshold"])
            )
            clean["recognition_threshold"] = max(0.25, min(0.80, threshold))
        except (TypeError, ValueError):
            pass
        try:
            clean["stable_frames"] = max(
                2, min(12, int(values.get("stable_frames", 4)))
            )
        except (TypeError, ValueError):
            pass
        try:
            clean["history_cooldown_seconds"] = max(
                5, min(3600, int(values.get("history_cooldown_seconds", 30)))
            )
        except (TypeError, ValueError):
            pass
        try:
            clean["min_face_size"] = max(
                32, min(320, int(values.get("min_face_size", 72)))
            )
        except (TypeError, ValueError):
            pass
        clean["camera_auto_start"] = bool(values.get("camera_auto_start", False))
        clean["theme"] = "light" if values.get("theme") == "light" else "dark"
        data_directory = str(values.get("data_directory", "") or "").strip()
        clean["data_directory"] = data_directory
        return clean

    def save(self) -> None:
        with self._lock:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps(self._values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, self.config_path)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return deepcopy(self._values.get(key, default))

    def update(self, **values: Any) -> None:
        with self._lock:
            self._values.update(values)
            self._values = self._validate(self._values)
            self.save()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._values)

    def data_directory(self) -> Path:
        configured = str(self.get("data_directory", "")).strip()
        if not configured:
            return default_data_dir()
        path = Path(configured).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".facevault_write_test"
            probe.write_text("ok", encoding="ascii")
            probe.unlink(missing_ok=True)
            return path.resolve()
        except OSError:
            logger.warning("配置的数据目录不可写，将回退到便携目录：%s", path)
            return default_data_dir()

    def reset(self) -> None:
        with self._lock:
            self._values = deepcopy(DEFAULT_SETTINGS)
            self.save()
        logger.warning("设置已恢复默认值")
