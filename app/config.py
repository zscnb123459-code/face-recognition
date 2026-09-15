"""Central configuration values and immutable defaults."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_RECOGNITION_THRESHOLD = 0.42
DEFAULT_STABLE_FRAMES = 4
DEFAULT_HISTORY_COOLDOWN_SECONDS = 30
DEFAULT_MIN_FACE_SIZE = 72
DEFAULT_DETECTION_SCORE = 0.75

SUPPORTED_RESOLUTIONS = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
}

THEME_LABELS = {"dark": "深色（推荐）", "light": "浅色"}


@dataclass(frozen=True)
class RecognitionSettings:
    threshold: float = DEFAULT_RECOGNITION_THRESHOLD
    stable_frames: int = DEFAULT_STABLE_FRAMES
    history_cooldown_seconds: int = DEFAULT_HISTORY_COOLDOWN_SECONDS
    min_face_size: int = DEFAULT_MIN_FACE_SIZE
    detection_score: float = DEFAULT_DETECTION_SCORE
