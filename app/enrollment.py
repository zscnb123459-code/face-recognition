"""Guided local enrollment worker. Only embeddings leave this worker."""

from __future__ import annotations

import platform
import threading
import time
from typing import Final

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from app.config import SUPPORTED_RESOLUTIONS
from app.models import EnrollmentSample, FaceObservation
from app.recognition import FaceEngine, FaceEngineError
from app.services.settings_service import SettingsService
from app.utils.image_utils import assess_face_quality
from app.utils.logging_setup import get_logger

logger = get_logger("enrollment")
WINDOWS_BACKENDS: Final[tuple[int, ...]] = (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)
ENROLLMENT_ANGLES: Final[tuple[str, ...]] = (
    "正面",
    "稍微向左转",
    "稍微向右转",
    "稍微抬头",
    "稍微低头",
)


class EnrollmentWorker(QObject):
    frame_ready = Signal(object, object)
    state_changed = Signal(bool, str)
    guidance_changed = Signal(bool, str, int, int)
    angle_captured = Signal(str, int, int)
    completed = Signal(object)
    error_occurred = Signal(str, str)

    def __init__(self, settings: SettingsService):
        super().__init__()
        self.settings = settings
        self._start_event = threading.Event()
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._capture_request = threading.Event()
        self._engine: FaceEngine | None = None
        self._capture: cv2.VideoCapture | None = None
        self._samples: list[EnrollmentSample] = []
        self._angle_index = 0
        self._angle_samples = 0

    @Slot()
    def run(self) -> None:
        try:
            self._engine = FaceEngine(detection_score=0.72)
            logger.info("录入模块模型已加载")
        except FaceEngineError as exc:
            self.error_occurred.emit("模型加载失败", str(exc))
            return

        while not self._shutdown_event.is_set():
            if not self._start_event.wait(0.1):
                continue
            self._start_event.clear()
            self._stop_event.clear()
            self._camera_loop()
        self._release_camera()
        self.state_changed.emit(False, "摄像头已关闭")

    def start_camera(self) -> None:
        self._stop_event.clear()
        self._start_event.set()

    def stop_camera(self) -> None:
        self._stop_event.set()
        self._start_event.clear()

    def request_capture(self) -> None:
        if self._angle_index < len(ENROLLMENT_ANGLES):
            self._capture_request.set()

    def reset_samples(self) -> None:
        self._samples = []
        self._angle_index = 0
        self._angle_samples = 0

    def shutdown(self) -> None:
        self._shutdown_event.set()
        self.stop_camera()

    def _camera_loop(self) -> None:
        config = self.settings.snapshot()
        self._capture = self._open_camera(int(config.get("camera_index", 0)))
        if self._capture is None:
            self.error_occurred.emit(
                "无法启动摄像头",
                "未检测到摄像头，或被其他程序占用。请检查 Windows 相机权限和设备连接。",
            )
            self.state_changed.emit(False, "摄像头不可用")
            return

        resolution = str(config.get("resolution", "1280x720"))
        width, height = SUPPORTED_RESOLUTIONS.get(resolution, (1280, 720))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        fps_limit = max(5, min(60, int(config.get("fps_limit", 30))))
        self.state_changed.emit(True, "录入摄像头正在使用")
        self._angle_index = 0
        self._angle_samples = 0
        self._samples = []
        self.guidance_changed.emit(False, "请将面部置于画面中央", 0, 3)

        while not self._stop_event.is_set() and not self._shutdown_event.is_set():
            started = time.perf_counter()
            ok, frame = self._capture.read()
            if not ok or frame is None:
                self.error_occurred.emit("摄像头中断", "无法继续读取摄像头画面。")
                break

            observations = self._detect_preview(
                frame, int(config.get("min_face_size", 72))
            )
            valid_face = False
            message = "未检测到人脸，请正对摄像头"
            if len(observations) > 1:
                message = "检测到多张人脸，请确保画面中只有您一人"
            elif len(observations) == 1:
                observation = observations[0]
                valid_face = not observation.quality_message
                message = (
                    observation.quality_message
                    or "请保持当前角度，然后点击“采集此角度”"
                )

            self.guidance_changed.emit(valid_face, message, self._angle_samples, 3)

            if self._capture_request.is_set():
                self._capture_request.clear()
                if valid_face and len(observations) == 1:
                    self._collect_current_angle(frame, observations[0], config)
                else:
                    self.error_occurred.emit("暂时无法采集", message)

            self.frame_ready.emit(frame, observations)
            target_interval = 1.0 / fps_limit
            remaining = target_interval - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)

        self._release_camera()
        if not self._shutdown_event.is_set():
            self.state_changed.emit(False, "录入摄像头已关闭")

    def _detect_preview(
        self, frame: np.ndarray, min_face_size: int
    ) -> list[FaceObservation]:
        assert self._engine is not None
        faces = self._engine.detect(frame)
        observations: list[FaceObservation] = []
        for face in faces:
            x, y, width, height = (round(value) for value in face[:4])
            bbox = (x, y, max(1, width), max(1, height))
            quality, message = assess_face_quality(
                frame, bbox, min_face_size, float(face[-1])
            )
            observations.append(
                FaceObservation(
                    bbox=bbox,
                    person_id=None,
                    name="",
                    similarity=None,
                    recognized=False,
                    stable=True,
                    quality_score=quality,
                    quality_message=message,
                    meta={"raw_face": face},
                )
            )
        return observations

    def _collect_current_angle(
        self,
        frame: np.ndarray,
        observation: FaceObservation,
        config: dict,
    ) -> None:
        assert self._engine is not None
        angle = ENROLLMENT_ANGLES[self._angle_index]
        raw_face = observation.meta.get("raw_face")
        if raw_face is None:
            self.error_occurred.emit("采集失败", "检测数据不完整，请重试。")
            return

        collected = 0
        attempts = 0
        while collected < 3 and attempts < 9 and not self._stop_event.is_set():
            attempts += 1
            if attempts > 1:
                ok, fresh_frame = self._capture.read()
                if not ok or fresh_frame is None:
                    break
            else:
                fresh_frame = frame
            try:
                faces = self._engine.detect(fresh_frame)
            except FaceEngineError:
                continue
            if len(faces) != 1:
                time.sleep(0.10)
                continue
            face = faces[0]
            bbox = tuple(round(value) for value in face[:4])
            quality, quality_message = assess_face_quality(
                fresh_frame,
                bbox,
                int(config.get("min_face_size", 72)),
                float(face[-1]),
            )
            if quality_message or quality < 0.48:
                time.sleep(0.10)
                continue
            try:
                embedding = self._engine.extract_embedding(fresh_frame, face)
            except FaceEngineError:
                continue
            self._samples.append(
                EnrollmentSample(embedding=embedding, quality=quality, angle=angle)
            )
            collected += 1
            self._angle_samples = collected
            self.angle_captured.emit(angle, collected, 3)
            time.sleep(0.18)

        if collected == 0:
            self.error_occurred.emit(
                "采集失败", "未能获得清晰样本，请调整光线和位置后重试。"
            )
            return

        self._angle_index += 1
        self._angle_samples = 0
        if self._angle_index >= len(ENROLLMENT_ANGLES):
            self.guidance_changed.emit(True, "全部角度采集完成", 3, 3)
            self.completed.emit(list(self._samples))
            self.stop_camera()
        else:
            next_angle = ENROLLMENT_ANGLES[self._angle_index]
            self.guidance_changed.emit(
                True,
                f"下一步：{next_angle}。调整到位后点击“采集此角度”",
                0,
                3,
            )

    def _open_camera(self, camera_index: int) -> cv2.VideoCapture | None:
        backends = (
            WINDOWS_BACKENDS if platform.system() == "Windows" else (cv2.CAP_ANY,)
        )
        for backend in backends:
            if self._shutdown_event.is_set() or self._stop_event.is_set():
                return None
            capture = (
                cv2.VideoCapture(camera_index, backend)
                if backend != cv2.CAP_ANY
                else cv2.VideoCapture(camera_index)
            )
            if capture.isOpened():
                return capture
            capture.release()
        return None

    def _release_camera(self) -> None:
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()
