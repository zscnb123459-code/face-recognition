"""People management page."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import PersonRecord
from app.ui.widgets import AvatarWidget, Card, PageHeader


def _display_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


class PeoplePage(QWidget):
    add_requested = Signal()
    rename_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._people: list[PersonRecord] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(
            PageHeader("People", "管理本地人员档案；原始录入画面不会长期保存。")
        )
        header.addStretch()
        self.add_button = QPushButton("＋ Add Person")
        self.add_button.setProperty("variant", "primary")
        header.addWidget(self.add_button)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        table_card = Card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)
        table_layout.setSpacing(10)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索姓名…")
        self.count_label = QLabel("0 人")
        self.count_label.setProperty("role", "muted")
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.count_label)
        table_layout.addLayout(search_row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["人员", "人脸数据", "录入时间", "更新时间"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table_layout.addWidget(self.table, 1)
        body.addWidget(table_card, 3)

        detail_card = Card()
        detail_card.setMinimumWidth(290)
        detail_card.setMaximumWidth(360)
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(10)
        detail_title = QLabel("档案详情")
        detail_title.setProperty("role", "section")
        self.avatar = AvatarWidget("?", 72)
        self.name_label = QLabel("尚未选择人员")
        self.name_label.setProperty("role", "title")
        self.status_label = QLabel("请从左侧列表选择档案")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        detail_layout.addWidget(detail_title)
        detail_layout.addSpacing(8)
        detail_layout.addWidget(self.avatar, 0, Qt.AlignHCenter)
        detail_layout.addWidget(self.name_label, 0, Qt.AlignHCenter)
        detail_layout.addWidget(self.status_label, 0, Qt.AlignHCenter)
        detail_layout.addSpacing(12)
        self.created_value = QLabel("--")
        self.updated_value = QLabel("--")
        self.embedding_value = QLabel("--")
        for caption, value in (
            ("录入时间", self.created_value),
            ("更新时间", self.updated_value),
            ("特征状态", self.embedding_value),
        ):
            row = QHBoxLayout()
            label = QLabel(caption)
            label.setProperty("role", "muted")
            value.setAlignment(Qt.AlignRight)
            row.addWidget(label)
            row.addStretch()
            row.addWidget(value)
            detail_layout.addLayout(row)
        detail_layout.addStretch()
        self.rename_button = QPushButton("修改名称")
        self.delete_button = QPushButton("删除人员档案")
        self.delete_button.setProperty("variant", "danger")
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        detail_layout.addWidget(self.rename_button)
        detail_layout.addWidget(self.delete_button)
        body.addWidget(detail_card, 1)
        root.addLayout(body, 1)

        self.add_button.clicked.connect(self.add_requested)
        self.search.textChanged.connect(self._apply_filter)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.rename_button.clicked.connect(self._request_rename)
        self.delete_button.clicked.connect(self._request_delete)

    def set_people(self, people: list[PersonRecord]) -> None:
        self._people = list(people)
        selected_id = self.selected_person_id()
        self._apply_filter()
        if selected_id is not None:
            self._select_id(selected_id)
        elif self.table.rowCount():
            self.table.selectRow(0)

    def selected_person_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def _apply_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        visible = [
            person
            for person in self._people
            if not needle or needle in person.name.casefold()
        ]
        self.table.setRowCount(len(visible))
        for row, person in enumerate(visible):
            name_item = QTableWidgetItem(person.name)
            name_item.setData(Qt.UserRole, person.id)
            self.table.setItem(row, 0, name_item)
            self.table.setCellWidget(row, 0, self._person_cell(person))
            self.table.setItem(
                row, 1, QTableWidgetItem(f"{person.embedding_count} 个特征")
            )
            self.table.setItem(
                row, 2, QTableWidgetItem(_display_time(person.created_at))
            )
            self.table.setItem(
                row, 3, QTableWidgetItem(_display_time(person.updated_at))
            )
        self.count_label.setText(f"{len(visible)} 人")
        if not visible:
            self._clear_detail()

    @staticmethod
    def _person_cell(person: PersonRecord) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(9)
        avatar = AvatarWidget(person.name, 34)
        label = QLabel(person.name)
        layout.addWidget(avatar)
        layout.addWidget(label)
        layout.addStretch()
        return widget

    def _select_id(self, person_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and int(item.data(Qt.UserRole)) == person_id:
                self.table.selectRow(row)
                return

    def _selection_changed(self) -> None:
        person_id = self.selected_person_id()
        person = next((item for item in self._people if item.id == person_id), None)
        if person is None:
            self._clear_detail()
            return
        self.avatar.set_name(person.name)
        self.name_label.setText(person.name)
        self.status_label.setText("已启用本地识别")
        self.status_label.setStyleSheet("color:#43d6a3;")
        self.created_value.setText(_display_time(person.created_at))
        self.updated_value.setText(_display_time(person.updated_at))
        self.embedding_value.setText(f"{person.embedding_count} 个有效样本")
        self.rename_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def _clear_detail(self) -> None:
        self.avatar.set_name("?")
        self.name_label.setText("尚未选择人员")
        self.status_label.setText("请从左侧列表选择档案")
        self.status_label.setStyleSheet("")
        self.created_value.setText("--")
        self.updated_value.setText("--")
        self.embedding_value.setText("--")
        self.rename_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def _request_rename(self) -> None:
        person_id = self.selected_person_id()
        if person_id is not None:
            self.rename_requested.emit(person_id)

    def _request_delete(self) -> None:
        person_id = self.selected_person_id()
        if person_id is not None:
            self.delete_requested.emit(person_id)
