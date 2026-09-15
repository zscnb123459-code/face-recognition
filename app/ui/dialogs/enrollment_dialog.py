"""Guided camera enrollment dialog."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from app.enrollment import ENROLLMENT_ANGLES, EnrollmentWorker
from app.models import EnrollmentSample, FaceObservation, FramePacket
from app.services.settings_service import SettingsService
from app.ui.widgets import CameraCanvas, Card


class EnrollmentDialog(QDialog):
    save_requested = Signal(str, object)

    def __init__(self, settings: SettingsService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FaceVault · 录入人员")
        self.setModal(True)
        self.resize(1020, 680)
        self.setMinimumSize(860, 580)
        self._samples: list[EnrollmentSample] = []
        self._camera_active = False
        self._guidance_ok = False

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("录入新人员")
        title.setProperty("role", "title")
        subtitle = QLabel(
            "五个角度，每个角度自动采集 3 个特征样本；不会保存这些摄像头画面。"
        )
        subtitle.setProperty("role", "muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        self.privacy_badge = QLabel("● 本地处理")
        self.privacy_badge.setStyleSheet(
            "color:#43d6a3; background:#43d6a31c; border-radius:13px; padding:5px 11px; font-weight:650;"
        )
        header.addLayout(heading)
        header.addStretch()
        header.addWidget(self.privacy_badge)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(14)
        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(10)
        self.canvas = CameraCanvas(compact=True)
        self.canvas.setMinimumSize(520, 340)
        self.guidance_label = QLabel("请输入姓名，然后点击“开始录入”")
        self.guidance_label.setWordWrap(True)
        self.guidance_label.setAlignment(Qt.AlignCenter)
        self.guidance_label.setProperty("role", "muted")
        self.guidance_label.setMinimumHeight(48)
        preview_layout.addWidget(self.canvas, 1)
        preview_layout.addWidget(self.guidance_label)
        content.addWidget(preview_card, 3)

        side = Card()
        side.setFixedWidth(310)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.setSpacing(10)
        name_label = QLabel("人员姓名")
        name_label.setProperty("role", "section")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：Cheng")
        self.name_edit.setMaxLength(40)
        side_layout.addWidget(name_label)
        side_layout.addWidget(self.name_edit)
        side_layout.addSpacing(4)

        progress_title = QLabel("采集进度")
        progress_title.setProperty("role", "section")
        self.progress = QProgressBar()
        self.progress.setRange(0, len(ENROLLMENT_ANGLES) * 3)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.stage_label = QLabel("等待开始")
        self.stage_label.setProperty("role", "muted")
        side_layout.addWidget(progress_title)
        side_layout.addWidget(self.progress)
        side_layout.addWidget(self.stage_label)

        self.angle_rows: list[tuple[QLabel, QLabel]] = []
        for angle in ENROLLMENT_ANGLES:
            row = QFrame()
            row.setProperty("card", "soft")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(10, 7, 10, 7)
            name = QLabel(angle)
            state = QLabel("待采集")
            state.setProperty("role", "muted")
            row_layout.addWidget(name)
            row_layout.addStretch()
            row_layout.addWidget(state)
            side_layout.addWidget(row)
            self.angle_rows.append((name, state))
        side_layout.addStretch()
        hint = QLabel("确保光线均匀，脸不要过小，画面中只出现您一人。")
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        side_layout.addWidget(hint)
        content.addWidget(side)
        root.addLayout(content, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        self.cancel_button = QPushButton("取消")
        self.start_button = QPushButton("开始录入")
        self.start_button.setProperty("variant", "primary")
        self.capture_button = QPushButton("采集此角度")
        self.capture_button.setProperty("variant", "blue")
        self.capture_button.setEnabled(False)
        self.save_button = QPushButton("保存本地档案")
        self.save_button.setProperty("variant", "primary")
        self.save_button.setEnabled(False)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.start_button)
        footer.addWidget(self.capture_button)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

        self.save_button.setVisible(False)
        self.cancel_button.clicked.connect(self.reject)
        self.start_button.clicked.connect(self._start_camera)
        self.capture_button.clicked.connect(self._request_capture)
        self.save_button.clicked.connect(self._request_save)

        self.thread = QThread(self)
        self.thread.setObjectName("FaceVaultEnrollmentThread")
        self.worker = EnrollmentWorker(settings)
        self.worker.moveToThread(self.thread)
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.state_changed.connect(self._on_state)
        self.worker.guidance_changed.connect(self._on_guidance)
        self.worker.angle_captured.connect(self._on_angle_sample)
        self.worker.completed.connect(self._on_completed)
        self.worker.error_occurred.connect(self._on_error)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _start_camera(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "姓名为空", "请先输入人员姓名。")
            self.name_edit.setFocus()
            return
        self.start_button.setEnabled(False)
        self.name_edit.setEnabled(False)
        self.worker.reset_samples()
        self.worker.start_camera()

    def _request_capture(self) -> None:
        if not self._camera_active or not self._guidance_ok:
            return
        self.capture_button.setEnabled(False)
        self.worker.request_capture()

    def _request_save(self) -> None:
        if not self._samples:
            return
        self.save_button.setEnabled(False)
        self.save_button.setText("正在保存…")
        self.save_requested.emit(self.name_edit.text().strip(), list(self._samples))

    def accept_saved(self) -> None:
        QMessageBox.information(
            self,
            "Enrollment Completed",
            f"已保存 {self.name_edit.text().strip()} 的本地人脸档案。",
        )
        self.accept()

    def show_save_error(self, message: str) -> None:
        self.save_button.setEnabled(True)
        self.save_button.setText("保存本地档案")
        QMessageBox.critical(self, "保存失败", message)

    def _on_frame(self, frame, observations: list[FaceObservation]) -> None:
        packet = FramePacket(
            frame=frame,
            observations=observations,
            fps=0.0,
            processing_ms=0.0,
            timestamp=datetime.now().astimezone(),
        )
        self.canvas.set_packet(packet)

    def _on_state(self, active: bool, message: str) -> None:
        self._camera_active = active
        if active:
            self.guidance_label.setText(message)
            self.capture_button.setEnabled(False)
        else:
            self.canvas.clear_frame(message)

    def _on_guidance(self, valid: bool, message: str, current: int, total: int) -> None:
        self._guidance_ok = valid
        self.guidance_label.setText(message)
        self.capture_button.setEnabled(
            valid and self._camera_active and not self.save_button.isVisible()
        )
        if current:
            self.stage_label.setText(f"当前角度已采集 {current}/{total} 个样本")

    def _on_angle_sample(self, angle: str, current: int, total: int) -> None:
        try:
            index = ENROLLMENT_ANGLES.index(angle)
        except ValueError:
            return
        self.progress.setValue(index * total + current)
        _, state = self.angle_rows[index]
        state.setText(f"{current}/{total}")
        state.setStyleSheet("color:#43d6a3; font-weight:650;")
        self.stage_label.setText(f"{angle}：{current}/{total}")

    def _on_completed(self, samples: list[EnrollmentSample]) -> None:
        self._samples = list(samples)
        for _, state in self.angle_rows:
            state.setText("完成")
            state.setStyleSheet("color:#43d6a3; font-weight:650;")
        self.progress.setValue(self.progress.maximum())
        self.stage_label.setText("Enrollment Completed")
        self.capture_button.setVisible(False)
        self.save_button.setVisible(True)
        self.save_button.setEnabled(True)
        self.guidance_label.setText(
            "采集完成。保存后会生成本地特征档案，不会保存原始录入照片。"
        )

    def _on_error(self, title: str, message: str) -> None:
        if self.isVisible():
            QMessageBox.warning(self, title, message)

    def closeEvent(self, event) -> None:
        self._shutdown_worker()
        super().closeEvent(event)

    def reject(self) -> None:
        self._shutdown_worker()
        super().reject()

    def _shutdown_worker(self) -> None:
        if not hasattr(self, "worker"):
            return
        self.worker.shutdown()
        self.thread.quit()
        if not self.thread.wait(3500):
            self.thread.terminate()
            self.thread.wait(500)
