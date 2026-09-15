"""Recognition history page."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import HistoryRecord
from app.ui.widgets import Card, PageHeader


class HistoryPage(QWidget):
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[HistoryRecord] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(
            PageHeader(
                "History", "识别事件保留在本地 SQLite 中；清除后将从数据库物理删除。"
            )
        )
        header.addStretch()
        self.clear_button = QPushButton("Clear History")
        self.clear_button.setProperty("variant", "danger")
        header.addWidget(self.clear_button)
        root.addLayout(header)

        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)
        filter_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部记录", "all")
        self.filter_combo.addItem("识别成功", "matched")
        self.filter_combo.addItem("Unknown", "unknown")
        self.count_label = QLabel("0 条")
        self.count_label.setProperty("role", "muted")
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()
        filter_row.addWidget(self.count_label)
        card_layout.addLayout(filter_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["时间", "识别结果", "是否匹配", "Similarity", "摄像头状态"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        card_layout.addWidget(self.table, 1)
        root.addWidget(card, 1)

        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        self.clear_button.clicked.connect(self.clear_requested)

    @staticmethod
    def _time_text(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

    def set_records(self, records: list[HistoryRecord]) -> None:
        self._records = list(records)
        self._apply_filter()

    def _apply_filter(self) -> None:
        mode = self.filter_combo.currentData()
        if mode == "matched":
            records = [record for record in self._records if record.matched]
        elif mode == "unknown":
            records = [record for record in self._records if not record.matched]
        else:
            records = self._records
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            time_item = QTableWidgetItem(self._time_text(record.created_at))
            name_item = QTableWidgetItem(record.label if record.matched else "Unknown")
            match_item = QTableWidgetItem("是" if record.matched else "否")
            similarity_item = QTableWidgetItem(
                f"{record.similarity:.4f}" if record.similarity is not None else "--"
            )
            camera_item = QTableWidgetItem(
                "摄像头开启"
                if record.camera_status == "camera_on"
                else record.camera_status
            )
            if record.matched:
                name_item.setForeground(Qt.GlobalColor.green)
            else:
                name_item.setForeground(Qt.GlobalColor.yellow)
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, match_item)
            self.table.setItem(row, 3, similarity_item)
            self.table.setItem(row, 4, camera_item)
        self.count_label.setText(f"{len(records)} 条")
