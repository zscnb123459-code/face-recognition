"""Small dialogs for names and deliberate destructive actions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class PersonNameDialog(QDialog):
    def __init__(self, title: str, prompt: str, name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        heading = QLabel(title)
        heading.setProperty("role", "title")
        description = QLabel(prompt)
        description.setWordWrap(True)
        description.setProperty("role", "muted")
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("请输入 1-40 个字符的姓名")
        self.name_edit.setMaxLength(40)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self.name_edit)
        layout.addWidget(buttons)
        self.name_edit.selectAll()

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "姓名为空", "请输入人员姓名。")
            return
        self.accept()

    def value(self) -> str:
        return self.name_edit.text().strip()


class DangerConfirmDialog(QDialog):
    def __init__(
        self, title: str, details: str, confirm_phrase: str = "确认删除", parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.confirm_phrase = confirm_phrase
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        heading = QLabel(title)
        heading.setProperty("role", "title")
        warning = QLabel("危险操作")
        warning.setProperty("role", "danger")
        description = QLabel(details)
        description.setWordWrap(True)
        prompt = QLabel(f"此操作不可撤销。请输入“{confirm_phrase}”继续：")
        prompt.setProperty("role", "muted")
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setPlaceholderText(confirm_phrase)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        danger_button = QPushButton("永久执行")
        danger_button.setProperty("variant", "danger")
        buttons.addButton(danger_button, QDialogButtonBox.AcceptRole)
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.rejected.connect(self.reject)
        danger_button.clicked.connect(self._confirm)
        layout.addWidget(heading)
        layout.addWidget(warning)
        layout.addWidget(description)
        layout.addWidget(prompt)
        layout.addWidget(self.confirm_edit)
        layout.addWidget(buttons)

    def _confirm(self) -> None:
        if self.confirm_edit.text().strip() != self.confirm_phrase:
            QMessageBox.warning(
                self, "确认文字不匹配", f"请输入“{self.confirm_phrase}”后才能执行。"
            )
            self.confirm_edit.setFocus()
            return
        self.accept()


class PrivacyStartupDialog(QDialog):
    def __init__(self, remembered: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FaceVault 隐私提示")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.choice = "closed"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        title = QLabel("摄像头与本地数据")
        title.setProperty("role", "title")
        body = QLabel(
            "FaceVault 默认不联网，也不会上传人脸数据。\n\n"
            "• 只有您点击“开启摄像头”后，程序才会访问摄像头。\n"
            "• 人物档案只保存人脸特征和姓名，不长期保存原始照片。\n"
            "• Unknown 人脸不会自动建档或自动保存。\n"
            "• 关闭程序或点击“停止摄像头”会立即释放设备。"
        )
        body.setWordWrap(True)
        body.setProperty("role", "muted")
        note = QLabel("你可以随时在“设置”中关闭自动启动并删除本地数据。")
        note.setProperty("role", "muted")
        buttons = QHBoxLayout()
        keep = QPushButton("保持关闭")
        keep.setProperty("variant", "ghost")
        start = QPushButton("按设置开启摄像头")
        start.setProperty("variant", "primary")
        keep.clicked.connect(self._choose_closed)
        start.clicked.connect(self._choose_start)
        buttons.addWidget(keep)
        buttons.addStretch()
        buttons.addWidget(start)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(note)
        layout.addLayout(buttons)

    def _choose_closed(self) -> None:
        self.choice = "closed"
        self.accept()

    def _choose_start(self) -> None:
        self.choice = "start"
        self.accept()
