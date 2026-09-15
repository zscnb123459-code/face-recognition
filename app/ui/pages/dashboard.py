"""Dashboard page."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models import FramePacket, HistoryRecord
from app.ui.widgets import CameraCanvas, Card, PageHeader, StatCard


class DashboardPage(QWidget):
    open_recognition_requested = Signal()
    open_people_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader("Dashboard", "实时掌握摄像头、识别与本地档案状态。")
        )

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.people_card = StatCard(
            "Registered People", "0", "本地已登记人员", "#43d6a3"
        )
        self.today_card = StatCard("Recognitions Today", "0", "今日成功匹配", "#55a9ff")
        self.unknown_card = StatCard("Unknown", "0", "今日未登记人脸", "#f6ba58")
        self.camera_card = StatCard(
            "Camera Status", "Offline", "摄像头未开启", "#8d9caf"
        )
        cards.addWidget(self.people_card, 0, 0)
        cards.addWidget(self.today_card, 0, 1)
        cards.addWidget(self.unknown_card, 0, 2)
        cards.addWidget(self.camera_card, 0, 3)
        for column in range(4):
            cards.setColumnStretch(column, 1)
        layout.addLayout(cards)

        content = QHBoxLayout()
        content.setSpacing(14)
        preview_card = Card()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)
        preview_header = QHBoxLayout()
        preview_title = QLabel("实时预览")
        preview_title.setProperty("role", "section")
        self.preview_status = QLabel("摄像头已关闭")
        self.preview_status.setProperty("role", "muted")
        open_button = QPushButton("打开识别页")
        open_button.setProperty("variant", "ghost")
        open_button.clicked.connect(self.open_recognition_requested)
        preview_header.addWidget(preview_title)
        preview_header.addWidget(self.preview_status)
        preview_header.addStretch()
        preview_header.addWidget(open_button)
        self.canvas = CameraCanvas(compact=True)
        preview_layout.addLayout(preview_header)
        preview_layout.addWidget(self.canvas, 1)
        content.addWidget(preview_card, 3)

        recent_card = Card()
        recent_card.setMinimumWidth(340)
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(16, 16, 16, 16)
        recent_header = QHBoxLayout()
        recent_title = QLabel("最近识别")
        recent_title.setProperty("role", "section")
        self.recent_count = QLabel("")
        self.recent_count.setProperty("role", "muted")
        recent_header.addWidget(recent_title)
        recent_header.addStretch()
        recent_header.addWidget(self.recent_count)
        self.recent_list = QListWidget()
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.setMinimumHeight(260)
        recent_layout.addLayout(recent_header)
        recent_layout.addWidget(self.recent_list, 1)
        content.addWidget(recent_card, 2)
        layout.addLayout(content, 1)

        status_card = Card()
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 14, 18, 14)
        self.model_status = QLabel("● 识别模型：正在初始化")
        self.model_status.setProperty("role", "warning")
        self.privacy_status = QLabel("● 本地处理 · 不在线上传 · Unknown 不建档")
        self.privacy_status.setProperty("role", "accent")
        self.storage_status = QLabel("System Status: Ready")
        self.storage_status.setProperty("role", "muted")
        status_layout.addWidget(self.model_status)
        status_layout.addStretch()
        status_layout.addWidget(self.storage_status)
        status_layout.addSpacing(18)
        status_layout.addWidget(self.privacy_status)
        layout.addWidget(status_card)
        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

    def set_counts(self, counts: dict[str, int]) -> None:
        self.people_card.set_value(
            str(counts.get("people", 0)), f"{counts.get('embeddings', 0)} 个本地特征"
        )
        self.today_card.set_value(str(counts.get("today_matched", 0)), "今日成功匹配")
        self.unknown_card.set_value(
            str(counts.get("today_unknown", 0)), "Unknown 不保存照片"
        )

    def set_camera_state(self, active: bool, message: str) -> None:
        self.camera_card.set_value("Online" if active else "Offline", message)
        self.preview_status.setText(message)
        if not active:
            self.canvas.clear_frame(message)

    def set_model_state(self, ok: bool, message: str) -> None:
        self.model_status.setText(f"● 识别模型：{message}")
        self.model_status.setProperty("role", "accent" if ok else "danger")
        self.model_status.style().unpolish(self.model_status)
        self.model_status.style().polish(self.model_status)

    def update_packet(self, packet: FramePacket) -> None:
        if self.isVisible():
            self.canvas.set_packet(packet)

    def set_history(self, records: list[HistoryRecord]) -> None:
        self.recent_list.clear()
        self.recent_count.setText(f"{len(records)} 条")
        for record in records[:6]:
            try:
                time_text = datetime.fromisoformat(record.created_at).strftime(
                    "%H:%M:%S"
                )
            except ValueError:
                time_text = record.created_at[11:19]
            prefix = "✓" if record.matched else "!"
            similarity = (
                f"{record.similarity:.2f}" if record.similarity is not None else "--"
            )
            item = QListWidgetItem(
                f"{prefix}  {time_text}   {record.label}   Similarity {similarity}"
            )
            item.setForeground(
                Qt.GlobalColor.white if record.matched else Qt.GlobalColor.yellow
            )
            self.recent_list.addItem(item)
