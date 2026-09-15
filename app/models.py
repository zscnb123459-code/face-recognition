"""Core data structures shared between UI and background workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PersonRecord:
    id: int
    name: str
    created_at: str
    updated_at: str
    embedding_count: int = 0


@dataclass(frozen=True)
class HistoryRecord:
    id: int
    person_id: int | None
    label: str
    similarity: float | None
    matched: bool
    camera_status: str
    created_at: str


@dataclass(frozen=True)
class FaceObservation:
    bbox: tuple[int, int, int, int]
    person_id: int | None
    name: str
    similarity: float | None
    recognized: bool
    stable: bool
    quality_score: float
    quality_message: str = ""
    track_id: int = -1
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FramePacket:
    frame: np.ndarray
    observations: list[FaceObservation]
    fps: float
    processing_ms: float
    timestamp: datetime


@dataclass(frozen=True)
class EnrollmentSample:
    embedding: np.ndarray
    quality: float
    angle: str
