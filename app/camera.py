"""Threaded camera capture and recognition pipeline."""

from __future__ import annotations

import platform
import threading
import time
from datetime import datetime
from typing import Final

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.config import SUPPORTED_RESOLUTIONS, RecognitionSettings
from app.database import Database, DatabaseError
from app.models import FaceObservation, FramePacket
from app.recognition import (
    FaceEngine,
    FaceEngineError,
    KnownFace,
    RecognitionStabilizer,
)
from app.services.settings_service import SettingsService
from app.utils.logging_setup import get_logger

logger = get_logger("camera")
WINDOWS_BACKENDS: Final[tuple[int, ...]] = (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY)


class CameraWorker(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(bool, str)
    model_ready = Signal(bool, str)
    error_occurred = Signal(str, str)
    metrics_changed = Signal(float, float)

    def __init__(self, database: Database, settings: SettingsService):
        super().__init__()
        self.database = database
        self.settings = settings
        self._start_event = threading.Event()
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._reload_event = threading.Event()
        self._capture: cv2.VideoCapture | None = None
        self._engine: FaceEngine | None = None
        self._known_faces: list[KnownFace] = []
        self._stabilizer = RecognitionStabilizer(settings.get("stable_frames", 4))
        self._last_history: dict[tuple[int | None, str], float] = {}

    @Slot()
    def run(self) -> None:
        try:
            self._initialize_model()
        except FaceEngineError as exc:
            logger.error("人脸模型初始化失败：%s", exc)
            self.model_ready.emit(False, str(exc))
        else:
            self.model_ready.emit(True, "识别模型已就绪")

        while not self._shutdown_event.is_set():
            if not self._start_event.wait(timeout=0.10):
                continue
            self._start_event.clear()
            self._stop_event.clear()
            self._capture_loop()

        self._release_camera()
        self.state_changed.emit(False, "摄像头已关闭")

    def _initialize_model(self) -> None:
        config = self.settings.snapshot()
        self._engine = FaceEngine(detection_score=0.75)
        self._stabilizer = RecognitionStabilizer(int(config.get("stable_frames", 4)))
        self._reload_known_faces()
        logger.info("人脸检测与识别模型已加载")

    def _reload_known_faces(self) -> None:
        try:
            records = self.database.get_known_embeddings()
            self._known_faces = [
                KnownFace(person_id=person_id, name=name, embedding=embedding)
                for person_id, name, embedding in records
            ]
            logger.info("已加载本地人脸特征数量=%d", len(self._known_faces))
        except (DatabaseError, OSError):
            logger.exception("加载本地人脸特征失败")
            self._known_faces = []

    def request_reload(self) -> None:
        self._reload_event.set()

    def start_camera(self) -> None:
        self._stop_event.clear()
        self._start_event.set()

    def stop_camera(self) -> None:
        self._stop_event.set()
        self._start_event.clear()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        self.stop_camera()

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
                logger.info("摄像头已打开，index=%d，backend=%s", camera_index, backend)
                return capture
            capture.release()
        return None

    def _capture_loop(self) -> None:
        if self._engine is None:
            self.error_occurred.emit(
                "模型不可用", "人脸识别模型未成功加载，无法启动摄像头。"
            )
            self.state_changed.emit(False, "模型不可用")
            return

        config = self.settings.snapshot()
        camera_index = int(config.get("camera_index", 0))
        self._capture = self._open_camera(camera_index)
        if self._capture is None:
            message = (
                "未检测到可用摄像头，或摄像头被其他程序占用。"
                "请检查 Windows“相机”权限和设备连接后重试。"
            )
            logger.warning("摄像头启动失败，index=%d", camera_index)
            self.error_occurred.emit("无法启动摄像头", message)
            self.state_changed.emit(False, "摄像头不可用")
            return

        resolution = str(config.get("resolution", "1280x720"))
        width, height = SUPPORTED_RESOLUTIONS.get(resolution, (1280, 720))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        fps_limit = max(5, min(60, int(config.get("fps_limit", 30))))
        self.state_changed.emit(True, "摄像头正在使用")
        self._reload_known_faces()
        self._stabilizer.reset()
        self._last_history.clear()

        frame_counter = 0
        fps_clock = time.perf_counter()
        measured_fps = 0.0
        processing_ms = 0.0
        while not self._stop_event.is_set() and not self._shutdown_event.is_set():
            loop_start = time.perf_counter()
            ok, frame = self._capture.read()
            if not ok or frame is None:
                logger.warning("摄像头读取帧失败")
                self.error_occurred.emit(
                    "摄像头中断", "无法继续读取摄像头画面，请检查设备连接。"
                )
                break

            if self._reload_event.is_set():
                self._reload_event.clear()
                self._reload_known_faces()

            process_start = time.perf_counter()
            try:
                observations = self._process_frame(frame, config)
                processing_ms = (time.perf_counter() - process_start) * 1000.0
                if observations:
                    self._log_stable_events(observations)
                packet = FramePacket(
                    frame=frame,
                    observations=observations,
                    fps=measured_fps,
                    processing_ms=processing_ms,
                    timestamp=datetime.now().astimezone(),
                )
                self.frame_ready.emit(packet)
            except FaceEngineError as exc:
                logger.warning("处理画面失败：%s", exc)
            except Exception:
                logger.exception("摄像头处理循环发生未预期错误")
                self.error_occurred.emit(
                    "视频处理异常", "程序已停止摄像头以避免持续出错，请查看日志。"
                )
                break

            frame_counter += 1
            now = time.perf_counter()
            elapsed = now - fps_clock
            if elapsed >= 0.75:
                measured_fps = frame_counter / elapsed
                frame_counter = 0
                fps_clock = now
                self.metrics_changed.emit(measured_fps, processing_ms)

            target_interval = 1.0 / fps_limit
            remaining = target_interval - (time.perf_counter() - loop_start)
            if remaining > 0:
                time.sleep(remaining)

        self._release_camera()
        if not self._shutdown_event.is_set():
            self.state_changed.emit(False, "摄像头已关闭")

    def _process_frame(self, frame: np.ndarray, config: dict) -> list[FaceObservation]:
        assert self._engine is not None
        process_frame, scale = self._resize_for_processing(frame)
        recognition_settings = RecognitionSettings(
            threshold=float(config.get("recognition_threshold", 0.42)),
            stable_frames=int(config.get("stable_frames", 4)),
            history_cooldown_seconds=int(config.get("history_cooldown_seconds", 30)),
            min_face_size=int(config.get("min_face_size", 72)),
        )
        raw_observations = self._engine.recognize(
            process_frame, self._known_faces, recognition_settings
        )
        if scale != 1.0:
            raw_observations = [
                self._scale_observation(item, scale) for item in raw_observations
            ]
        return self._stabilizer.update(raw_observations)

    @staticmethod
    def _resize_for_processing(
        frame: np.ndarray, max_width: int = 960
    ) -> tuple[np.ndarray, float]:
        height, width = frame.shape[:2]
        if width <= max_width:
            return frame, 1.0
        scale = max_width / float(width)
        resized = cv2.resize(
            frame, (max_width, round(height * scale)), interpolation=cv2.INTER_AREA
        )
        return resized, 1.0 / scale

    @staticmethod
    def _scale_observation(
        observation: FaceObservation, scale: float
    ) -> FaceObservation:
        x, y, width, height = observation.bbox
        bbox = (
            round(x * scale),
            round(y * scale),
            round(width * scale),
            round(height * scale),
        )
        return FaceObservation(
            bbox=bbox,
            person_id=observation.person_id,
            name=observation.name,
            similarity=observation.similarity,
            recognized=observation.recognized,
            stable=observation.stable,
            quality_score=observation.quality_score,
            quality_message=observation.quality_message,
            track_id=observation.track_id,
            meta=dict(observation.meta),
        )

    def _log_stable_events(self, observations: list[FaceObservation]) -> None:
        cooldown = int(self.settings.get("history_cooldown_seconds", 30))
        now = time.monotonic()
        for observation in observations:
            if not observation.stable:
                continue
            key = (observation.person_id, observation.name)
            if now - self._last_history.get(key, -10_000.0) < cooldown:
                continue
            try:
                self.database.add_recognition_history(
                    person_id=observation.person_id,
                    label=observation.name,
                    similarity=observation.similarity,
                    matched=observation.recognized,
                    camera_status="camera_on",
                )
            except (DatabaseError, OSError):
                logger.exception("写入识别历史失败")
                continue
            self._last_history[key] = now

    def _release_camera(self) -> None:
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()
            logger.info("摄像头资源已释放")


class CameraController(QObject):
    frame_ready = Signal(object)
    state_changed = Signal(bool, str)
    model_ready = Signal(bool, str)
    error_occurred = Signal(str, str)
    metrics_changed = Signal(float, float)

    def __init__(
        self,
        database: Database,
        settings: SettingsService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.thread = QThread(self)
        self.thread.setObjectName("FaceVaultCameraThread")
        self.worker = CameraWorker(database, settings)
        self.worker.moveToThread(self.thread)
        self.worker.frame_ready.connect(self.frame_ready)
        self.worker.state_changed.connect(self.state_changed)
        self.worker.model_ready.connect(self.model_ready)
        self.worker.error_occurred.connect(self.error_occurred)
        self.worker.metrics_changed.connect(self.metrics_changed)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def start(self) -> None:
        self.worker.start_camera()

    def stop(self) -> None:
        self.worker.stop_camera()

    def reload_people(self) -> None:
        self.worker.request_reload()

    def shutdown(self) -> None:
        self.worker.shutdown()
        self.thread.quit()
        if not self.thread.wait(4000):
            logger.error("摄像头线程未在超时前退出")
