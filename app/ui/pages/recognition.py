"""Live recognition page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models import FramePacket
from app.ui.widgets import CameraCanvas, Card, FaceSummaryPanel, PageHeader, StatusPill


class RecognitionPage(QWidget):
    start_camera_requested = Signal()
    stop_camera_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(
            PageHeader(
                "Recognition", "每张人脸独立检测；连续多帧结果一致后才会更新最终身份。"
            )
        )
        header.addStretch()
        self.status = StatusPill("摄像头关闭", False)
        self.start_button = QPushButton("开启摄像头")
        self.start_button.setProperty("variant", "primary")
        self.start_button.setEnabled(False)
        self.stop_button = QPushButton("立即停止识别")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setEnabled(False)
        header.addWidget(self.status)
        header.addWidget(self.start_button)
        header.addWidget(self.stop_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        self.canvas = CameraCanvas(compact=False)
        preview_layout.addWidget(self.canvas, 1)
        metrics = QHBoxLayout()
        self.fps_label = QLabel("FPS 0.0")
        self.processing_label = QLabel("Processing Time 0.0 ms")
        self.detection_label = QLabel("Faces 0")
        for label in (self.fps_label, self.processing_label, self.detection_label):
            label.setProperty("role", "muted")
        metrics.addWidget(self.fps_label)
        metrics.addSpacing(12)
        metrics.addWidget(self.processing_label)
        metrics.addStretch()
        metrics.addWidget(self.detection_label)
        preview_layout.addLayout(metrics)
        splitter.addWidget(preview_card)

        side = Card()
        side.setMinimumWidth(300)
        side.setMaximumWidth(390)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(16, 16, 16, 16)
        side_layout.setSpacing(12)
        self.face_panel = FaceSummaryPanel()
        side_layout.addWidget(self.face_panel)
        note = QLabel("Similarity 是模型特征相似度，不代表现实世界身份真实性概率。")
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        side_layout.addWidget(note)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 330])
        root.addWidget(splitter, 1)

        self.start_button.clicked.connect(self.start_camera_requested)
        self.stop_button.clicked.connect(self.stop_camera_requested)

    def set_camera_state(self, active: bool, message: str) -> None:
        self.status.set_state(active, message)
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        if not active:
            self.canvas.clear_frame(message)
            self.face_panel.set_observations([])

    def set_packet(self, packet: FramePacket) -> None:
        if not self.isVisible():
            return
        self.canvas.set_packet(packet)
        self.face_panel.set_observations(packet.observations)
        self.fps_label.setText(f"FPS {packet.fps:04.1f}")
        self.processing_label.setText(
            f"Processing Time {packet.processing_ms:05.1f} ms"
        )
        self.detection_label.setText(f"Faces {len(packet.observations)}")

    def set_model_state(self, ok: bool, message: str) -> None:
        self.start_button.setToolTip(message)
        if not ok:
            self.start_button.setEnabled(False)
