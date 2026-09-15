"""Settings page with privacy-sensitive actions."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import SUPPORTED_RESOLUTIONS, THEME_LABELS
from app.services.settings_service import SettingsService
from app.ui.widgets import Card, PageHeader


class SettingsPage(QWidget):
    save_requested = Signal(dict)
    open_data_directory_requested = Signal()
    change_data_directory_requested = Signal()
    delete_all_people_requested = Signal()
    clear_history_requested = Signal()
    reset_settings_requested = Signal()

    def __init__(self, settings: SettingsService, parent=None):
        super().__init__(parent)
        self.settings = settings
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(
            PageHeader(
                "Settings", "参数保存到本机；识别阈值集中配置，重启摄像头后完全生效。"
            )
        )
        header.addStretch()
        self.save_button = QPushButton("保存设置")
        self.save_button.setProperty("variant", "primary")
        header.addWidget(self.save_button)
        layout.addLayout(header)

        camera_card = Card()
        camera_form = QFormLayout(camera_card)
        camera_form.setContentsMargins(20, 18, 20, 18)
        camera_form.setSpacing(12)
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 32)
        self.camera_index.setToolTip("先尝试 0；如果无画面，可切换为 1、2 等")
        self.resolution = QComboBox()
        for label in SUPPORTED_RESOLUTIONS:
            self.resolution.addItem(label, label)
        self.fps_limit = QSpinBox()
        self.fps_limit.setRange(5, 60)
        self.fps_limit.setSuffix(" FPS")
        self.auto_start = QCheckBox("启动 FaceVault 后按隐私提示开启摄像头")
        camera_form.addRow("Camera Selection", self.camera_index)
        camera_form.addRow("Camera Resolution", self.resolution)
        camera_form.addRow("FPS Limit", self.fps_limit)
        camera_form.addRow("Start Camera Automatically", self.auto_start)
        layout.addWidget(camera_card)

        recognition_card = Card()
        recognition_form = QFormLayout(recognition_card)
        recognition_form.setContentsMargins(20, 18, 20, 18)
        recognition_form.setSpacing(12)
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.25, 0.80)
        self.threshold.setSingleStep(0.01)
        self.threshold.setDecimals(2)
        self.threshold.setToolTip(
            "SFace 余弦相似度阈值。提高可减少误识别，也更可能出现 Unknown。"
        )
        self.stable_frames = QSpinBox()
        self.stable_frames.setRange(2, 12)
        self.stable_frames.setSuffix(" 帧")
        self.cooldown = QSpinBox()
        self.cooldown.setRange(5, 3600)
        self.cooldown.setSuffix(" 秒")
        self.min_face = QSpinBox()
        self.min_face.setRange(32, 320)
        self.min_face.setSuffix(" px")
        recognition_form.addRow("Recognition Threshold", self.threshold)
        recognition_form.addRow("Stable Frames", self.stable_frames)
        recognition_form.addRow("History Cooldown", self.cooldown)
        recognition_form.addRow("Minimum Face Size", self.min_face)
        layout.addWidget(recognition_card)

        appearance_card = Card()
        appearance_form = QFormLayout(appearance_card)
        appearance_form.setContentsMargins(20, 18, 20, 18)
        self.theme = QComboBox()
        for key, label in THEME_LABELS.items():
            self.theme.addItem(label, key)
        appearance_form.addRow("Theme", self.theme)
        layout.addWidget(appearance_card)

        storage_card = Card()
        storage_layout = QVBoxLayout(storage_card)
        storage_layout.setContentsMargins(20, 18, 20, 18)
        storage_layout.setSpacing(10)
        storage_title = QLabel("Data Directory")
        storage_title.setProperty("role", "section")
        storage_note = QLabel("人物特征、识别历史、设置与日志均保存在此目录。")
        storage_note.setProperty("role", "muted")
        storage_row = QHBoxLayout()
        self.data_dir = QLineEdit()
        self.data_dir.setReadOnly(True)
        open_button = QPushButton("打开目录")
        change_button = QPushButton("更改目录")
        storage_row.addWidget(self.data_dir, 1)
        storage_row.addWidget(open_button)
        storage_row.addWidget(change_button)
        storage_layout.addWidget(storage_title)
        storage_layout.addWidget(storage_note)
        storage_layout.addLayout(storage_row)
        layout.addWidget(storage_card)

        danger_card = Card()
        danger_layout = QVBoxLayout(danger_card)
        danger_layout.setContentsMargins(20, 18, 20, 18)
        danger_layout.setSpacing(10)
        danger_title = QLabel("隐私与危险操作")
        danger_title.setProperty("role", "section")
        danger_note = QLabel(
            "以下操作会修改或永久删除本地数据，执行前需要输入确认文字。"
        )
        danger_note.setProperty("role", "muted")
        danger_layout.addWidget(danger_title)
        danger_layout.addWidget(danger_note)
        buttons = QHBoxLayout()
        clear_history_button = QPushButton("Clear Recognition History")
        clear_history_button.setProperty("variant", "danger")
        delete_people_button = QPushButton("Delete All People")
        delete_people_button.setProperty("variant", "danger")
        reset_button = QPushButton("Reset Settings")
        reset_button.setProperty("variant", "danger")
        buttons.addWidget(clear_history_button)
        buttons.addWidget(delete_people_button)
        buttons.addWidget(reset_button)
        buttons.addStretch()
        danger_layout.addLayout(buttons)
        layout.addWidget(danger_card)
        layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)

        self.save_button.clicked.connect(self._emit_save)
        open_button.clicked.connect(self.open_data_directory_requested)
        change_button.clicked.connect(self.change_data_directory_requested)
        clear_history_button.clicked.connect(self.clear_history_requested)
        delete_people_button.clicked.connect(self.delete_all_people_requested)
        reset_button.clicked.connect(self.reset_settings_requested)
        self.load_values()

    def set_data_directory(self, path: str) -> None:
        self.data_dir.setText(path)
        self.data_dir.setCursorPosition(0)

    def load_values(self) -> None:
        values = self.settings.snapshot()
        self.camera_index.setValue(int(values.get("camera_index", 0)))
        resolution = str(values.get("resolution", "1280x720"))
        self.resolution.setCurrentIndex(max(0, self.resolution.findData(resolution)))
        self.fps_limit.setValue(int(values.get("fps_limit", 30)))
        self.auto_start.setChecked(bool(values.get("camera_auto_start", False)))
        self.threshold.setValue(float(values.get("recognition_threshold", 0.42)))
        self.stable_frames.setValue(int(values.get("stable_frames", 4)))
        self.cooldown.setValue(int(values.get("history_cooldown_seconds", 30)))
        self.min_face.setValue(int(values.get("min_face_size", 72)))
        self.theme.setCurrentIndex(
            max(0, self.theme.findData(values.get("theme", "dark")))
        )
        self.set_data_directory(str(self.settings.data_directory()))

    def activate_for_theme(self, theme: str) -> None:
        index = self.theme.findData(theme)
        if index >= 0:
            self.theme.setCurrentIndex(index)

    def collect_values(self) -> dict:
        return {
            "camera_index": self.camera_index.value(),
            "resolution": self.resolution.currentData(),
            "fps_limit": self.fps_limit.value(),
            "camera_auto_start": self.auto_start.isChecked(),
            "recognition_threshold": round(self.threshold.value(), 2),
            "stable_frames": self.stable_frames.value(),
            "history_cooldown_seconds": self.cooldown.value(),
            "min_face_size": self.min_face.value(),
            "theme": self.theme.currentData(),
        }

    def _emit_save(self) -> None:
        self.save_requested.emit(self.collect_values())
