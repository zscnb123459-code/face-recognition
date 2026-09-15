"""Face detection, embedding extraction and multi-frame stabilization.

The implementation uses OpenCV's maintained YuNet and SFace models. It does
not infer age, gender, ethnicity, health or any other sensitive attribute.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from app.config import RecognitionSettings
from app.models import FaceObservation
from app.paths import resource_path
from app.utils.image_utils import assess_face_quality, bbox_iou
from app.utils.logging_setup import get_logger

logger = get_logger("recognition")


class FaceEngineError(RuntimeError):
    pass


def _ascii_model_path(source: Path) -> Path:
    """Return a model path that OpenCV can open on Windows.

    OpenCV's C++ narrow-path file APIs may fail when a source path contains
    Chinese characters. The model itself contains no user data, so it is
    safely cached under an ASCII-only public/temp directory when needed.
    """

    resolved = source.resolve()
    if all(ord(char) < 128 for char in str(resolved)):
        return resolved

    candidates = [
        Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "FaceVaultModelCache",
        Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        / "FaceVault"
        / "ModelCache",
        Path(tempfile.gettempdir()) / "FaceVaultModelCache",
    ]
    last_error: OSError | None = None
    for directory in candidates:
        try:
            if any(ord(char) >= 128 for char in str(directory.resolve())):
                continue
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / resolved.name
            if not target.exists() or target.stat().st_size != resolved.stat().st_size:
                shutil.copy2(resolved, target)
            return target
        except OSError as exc:
            last_error = exc
    raise FaceEngineError(f"无法为模型创建 ASCII 缓存路径：{last_error}")


@dataclass
class KnownFace:
    person_id: int
    name: str
    embedding: np.ndarray


@dataclass
class _Track:
    track_id: int
    bbox: tuple[int, int, int, int]
    history: deque[tuple[int | None, float]] = field(default_factory=deque)
    stable_key: tuple[int | None, str] | None = None
    stable_similarity: float | None = None
    misses: int = 0


class RecognitionStabilizer:
    """Require repeated consistent results before publishing an identity."""

    def __init__(self, stable_frames: int = 4, iou_threshold: float = 0.25):
        self.stable_frames = max(2, int(stable_frames))
        self.iou_threshold = iou_threshold
        self._tracks: dict[int, _Track] = {}
        self._next_track_id = 1

    @staticmethod
    def _center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x, y, width, height = bbox
        return x + width / 2.0, y + height / 2.0

    def _match_track(self, bbox: tuple[int, int, int, int]) -> _Track | None:
        best: _Track | None = None
        best_score = 0.0
        cx, cy = self._center(bbox)
        for track in self._tracks.values():
            overlap = bbox_iou(bbox, track.bbox)
            tx, ty = self._center(track.bbox)
            distance = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
            diagonal = max((bbox[2] ** 2 + bbox[3] ** 2) ** 0.5, 1.0)
            distance_score = max(0.0, 1.0 - distance / (diagonal * 1.25))
            score = max(overlap, distance_score * 0.8)
            if score > best_score:
                best = track
                best_score = score
        return best if best_score >= self.iou_threshold else None

    def update(self, observations: Sequence[FaceObservation]) -> list[FaceObservation]:
        for track in self._tracks.values():
            track.misses += 1

        results: list[FaceObservation] = []
        for observation in observations:
            track = self._match_track(observation.bbox)
            if track is None:
                track = _Track(
                    track_id=self._next_track_id,
                    bbox=observation.bbox,
                    history=deque(maxlen=self.stable_frames),
                )
                self._tracks[track.track_id] = track
                self._next_track_id += 1
            else:
                track.bbox = observation.bbox
                track.misses = 0

            key = (observation.person_id, observation.name)
            track.history.append((observation.person_id, observation.similarity or 0.0))
            stable = len(track.history) >= self.stable_frames and all(
                item[0] == key[0] for item in track.history
            )

            if stable:
                similarities = [item[1] for item in track.history if item[1] > 0]
                average_similarity = (
                    float(np.mean(similarities)) if similarities else None
                )
                track.stable_key = key
                track.stable_similarity = average_similarity
                output = FaceObservation(
                    bbox=observation.bbox,
                    person_id=observation.person_id,
                    name=observation.name,
                    similarity=average_similarity,
                    recognized=observation.recognized,
                    stable=True,
                    quality_score=observation.quality_score,
                    quality_message=observation.quality_message,
                    track_id=track.track_id,
                    meta=dict(observation.meta),
                )
            else:
                output = FaceObservation(
                    bbox=observation.bbox,
                    person_id=None,
                    name="确认中",
                    similarity=observation.similarity,
                    recognized=False,
                    stable=False,
                    quality_score=observation.quality_score,
                    quality_message=observation.quality_message,
                    track_id=track.track_id,
                    meta=dict(observation.meta),
                )
            results.append(output)

        stale_ids = [
            track_id for track_id, track in self._tracks.items() if track.misses > 15
        ]
        for track_id in stale_ids:
            self._tracks.pop(track_id, None)

        return results

    def reset(self) -> None:
        self._tracks.clear()
        self._next_track_id = 1


class FaceEngine:
    """Wrapper around OpenCV FaceDetectorYN and FaceRecognizerSF."""

    def __init__(
        self,
        detector_model: Path | None = None,
        recognizer_model: Path | None = None,
        detection_score: float = 0.75,
    ):
        detector_source = detector_model or resource_path(
            "models", "face_detection_yunet_2023mar.onnx"
        )
        recognizer_source = recognizer_model or resource_path(
            "models", "face_recognition_sface_2021dec.onnx"
        )
        self.detector_source_path = Path(detector_source)
        self.recognizer_source_path = Path(recognizer_source)
        self.detector_path = _ascii_model_path(self.detector_source_path)
        self.recognizer_path = _ascii_model_path(self.recognizer_source_path)
        self.detection_score = float(detection_score)
        self.detector = None
        self.recognizer = None
        self.input_size = (320, 320)
        self._load()

    def _load(self) -> None:
        missing = [
            path
            for path in (self.detector_path, self.recognizer_path)
            if not path.exists()
        ]
        if missing:
            names = "、".join(path.name for path in missing)
            raise FaceEngineError(f"识别模型文件不存在：{names}")
        try:
            self.detector = cv2.FaceDetectorYN.create(
                str(self.detector_path),
                "",
                self.input_size,
                score_threshold=self.detection_score,
                nms_threshold=0.3,
                top_k=5000,
            )
            self.recognizer = cv2.FaceRecognizerSF.create(str(self.recognizer_path), "")
        except cv2.error as exc:
            raise FaceEngineError(f"人脸模型加载失败：{exc}") from exc

    def detect(self, frame: np.ndarray) -> np.ndarray:
        if self.detector is None:
            raise FaceEngineError("人脸检测模型尚未初始化")
        height, width = frame.shape[:2]
        if self.input_size != (width, height):
            self.detector.setInputSize((width, height))
            self.input_size = (width, height)
        try:
            _, faces = self.detector.detect(frame)
        except cv2.error as exc:
            raise FaceEngineError(f"人脸检测失败：{exc}") from exc
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return np.asarray(faces, dtype=np.float32)

    def extract_embedding(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray:
        if self.recognizer is None:
            raise FaceEngineError("人脸识别模型尚未初始化")
        try:
            aligned = self.recognizer.alignCrop(frame, face)
            feature_method = getattr(self.recognizer, "feature", None) or getattr(
                self.recognizer, "getFeature", None
            )
            if feature_method is None:
                raise FaceEngineError("当前 OpenCV 版本不支持 SFace 特征提取接口")
            feature = feature_method(aligned)
        except cv2.error as exc:
            raise FaceEngineError(f"人脸特征提取失败：{exc}") from exc
        vector = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            raise FaceEngineError("提取到的人脸特征无效")
        return (vector / norm).reshape(1, -1)

    @staticmethod
    def compare(embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        left = np.asarray(embedding_a, dtype=np.float32).reshape(-1)
        right = np.asarray(embedding_b, dtype=np.float32).reshape(-1)
        left_norm = float(np.linalg.norm(left))
        right_norm = float(np.linalg.norm(right))
        if left_norm <= 1e-12 or right_norm <= 1e-12:
            return -1.0
        return float(np.dot(left / left_norm, right / right_norm))

    def recognize(
        self,
        frame: np.ndarray,
        known_faces: Sequence[KnownFace],
        settings: RecognitionSettings,
    ) -> list[FaceObservation]:
        faces = self.detect(frame)
        observations: list[FaceObservation] = []
        for index, face in enumerate(faces):
            x, y, width, height = (round(value) for value in face[:4])
            bbox = (x, y, max(1, width), max(1, height))
            quality, quality_message = assess_face_quality(
                frame,
                bbox,
                settings.min_face_size,
                detection_score=float(face[-1]),
            )
            person_id: int | None = None
            name = "Unknown"
            similarity: float | None = None
            recognized = False
            try:
                embedding = self.extract_embedding(frame, face)
                if known_faces:
                    best = max(
                        known_faces,
                        key=lambda item: self.compare(embedding, item.embedding),
                    )
                    similarity = self.compare(embedding, best.embedding)
                    if similarity >= settings.threshold and quality >= 0.30:
                        person_id = best.person_id
                        name = best.name
                        recognized = True
            except FaceEngineError as exc:
                quality_message = str(exc)
                logger.warning("单张人脸特征提取失败：%s", exc)

            observations.append(
                FaceObservation(
                    bbox=bbox,
                    person_id=person_id,
                    name=name,
                    similarity=similarity,
                    recognized=recognized,
                    stable=False,
                    quality_score=quality,
                    quality_message=quality_message,
                    meta={"detection_score": float(face[-1]), "face_index": index},
                )
            )
        return observations
