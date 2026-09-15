"""FaceVault main window and application orchestration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QProcess, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.camera import CameraController
from app.database import Database, DatabaseError
from app.models import EnrollmentSample
from app.paths import APP_DISPLAY_NAME, APP_SUBTITLE, APP_VERSION, is_frozen
from app.services.settings_service import SettingsService
from app.ui.dialogs.common import (
    DangerConfirmDialog,
    PersonNameDialog,
    PrivacyStartupDialog,
)
from app.ui.dialogs.enrollment_dialog import EnrollmentDialog
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.history import HistoryPage
from app.ui.pages.people import PeoplePage
from app.ui.pages.recognition import RecognitionPage
from app.ui.pages.settings import SettingsPage
from app.ui.theme import build_stylesheet
from app.ui.widgets import StatusPill
from app.utils.logging_setup import get_logger

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    NAV_ITEMS = (
        ("Dashboard", "◫"),
        ("People", "◎"),
        ("Recognition", "⌾"),
        ("History", "≡"),
        ("Settings", "⚙"),
    )

    def __init__(self, settings: SettingsService):
        super().__init__()
        self.settings = settings
        data_dir = self.settings.data_directory()
        self.database = Database(data_dir / "FaceVault.db")
        self.camera = CameraController(self.database, self.settings, self)
        self._camera_active = False
        self._model_ready = False
        self._pending_camera_start = False
        self._pending_enrollment = False
        self._resume_camera_after_enrollment = False
        self._enrollment_dialog: EnrollmentDialog | None = None
        self._page_animation: QPropertyAnimation | None = None

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(build_stylesheet(self.settings.get("theme", "dark")))
        self._build_ui()
        self._connect_signals()
        self._apply_theme()
        self.refresh_data()
        self.statusBar().setStyleSheet(
            "background:#090e14; color:#8d9caf; border-top:1px solid #263444;"
        )
        self.statusBar().showMessage(f"数据目录：{data_dir}")

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start()
        if os.environ.get("FACEVAULT_SKIP_STARTUP_DIALOG") != "1":
            QTimer.singleShot(250, self._show_startup_privacy)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(218)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 16)
        sidebar_layout.setSpacing(8)
        brand = QLabel("FaceVault")
        brand.setProperty("role", "brand")
        subtitle = QLabel(APP_SUBTITLE.upper())
        subtitle.setProperty("role", "brandSub")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(22)

        self.nav_buttons: list[QPushButton] = []
        for index, (label, icon) in enumerate(self.NAV_ITEMS):
            button = QPushButton(f"{icon}   {label}")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setProperty("nav", "true")
            button.clicked.connect(
                lambda checked=False, page=index: self.switch_page(page)
            )
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch()

        privacy_card = QFrame()
        privacy_card.setProperty("card", "soft")
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(12, 11, 12, 11)
        privacy_layout.setSpacing(3)
        privacy_title = QLabel("● 本地隐私模式")
        privacy_title.setProperty("role", "accent")
        privacy_text = QLabel("不联网上传\nUnknown 不建档\n不保存原始照片")
        privacy_text.setProperty("role", "muted")
        privacy_text.setWordWrap(True)
        privacy_layout.addWidget(privacy_title)
        privacy_layout.addWidget(privacy_text)
        sidebar_layout.addWidget(privacy_card)
        version = QLabel(f"v{APP_VERSION} · Windows")
        version.setProperty("role", "muted")
        version.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(version)
        shell.addWidget(sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(66)
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(22, 10, 22, 10)
        top_layout.setSpacing(10)
        self.page_name = QLabel("Dashboard")
        self.page_name.setProperty("role", "section")
        self.toast_label = QLabel("")
        self.toast_label.setProperty("role", "accent")
        self.model_pill = StatusPill("模型初始化中", False)
        self.camera_pill = StatusPill("摄像头关闭", False)
        self.start_button = QPushButton("开启摄像头")
        self.start_button.setProperty("variant", "primary")
        self.start_button.setEnabled(False)
        self.stop_button = QPushButton("Stop Camera")
        self.stop_button.setProperty("variant", "danger")
        self.stop_button.setEnabled(False)
        top_layout.addWidget(self.page_name)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.toast_label)
        top_layout.addStretch()
        top_layout.addWidget(self.model_pill)
        top_layout.addWidget(self.camera_pill)
        top_layout.addWidget(self.start_button)
        top_layout.addWidget(self.stop_button)
        right_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.people_page = PeoplePage()
        self.recognition_page = RecognitionPage()
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage(self.settings)
        for page in (
            self.dashboard_page,
            self.people_page,
            self.recognition_page,
            self.history_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)
        right_layout.addWidget(self.stack, 1)
        shell.addWidget(right, 1)
        self.nav_buttons[0].setChecked(True)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.camera.frame_ready.connect(self._on_frame)
        self.camera.state_changed.connect(self._on_camera_state)
        self.camera.model_ready.connect(self._on_model_state)
        self.camera.error_occurred.connect(self._show_error)
        self.recognition_page.start_camera_requested.connect(self.start_camera)
        self.recognition_page.stop_camera_requested.connect(self.stop_camera)
        self.dashboard_page.open_recognition_requested.connect(
            lambda: self.switch_page(2)
        )
        self.people_page.add_requested.connect(self.add_person)
        self.people_page.rename_requested.connect(self.rename_person)
        self.people_page.delete_requested.connect(self.delete_person)
        self.history_page.clear_requested.connect(self.clear_history)
        self.settings_page.save_requested.connect(self.save_settings)
        self.settings_page.open_data_directory_requested.connect(
            self.open_data_directory
        )
        self.settings_page.change_data_directory_requested.connect(
            self.change_data_directory
        )
        self.settings_page.delete_all_people_requested.connect(self.delete_all_people)
        self.settings_page.clear_history_requested.connect(self.clear_history)
        self.settings_page.reset_settings_requested.connect(self.reset_settings)

    def switch_page(self, index: int) -> None:
        if index < 0 or index >= self.stack.count():
            return
        self.stack.setCurrentIndex(index)
        self.page_name.setText(self.NAV_ITEMS[index][0])
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        page = self.stack.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        self._page_animation = QPropertyAnimation(effect, b"opacity", self)
        self._page_animation.setDuration(160)
        self._page_animation.setStartValue(0.35)
        self._page_animation.setEndValue(1.0)
        self._page_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._page_animation.start()
        if index == 2:
            self.recognition_page.start_button.setEnabled(
                self._model_ready and not self._camera_active
            )

    def _show_startup_privacy(self) -> None:
        dialog = PrivacyStartupDialog(
            bool(self.settings.get("camera_auto_start", False)), self
        )
        dialog.exec()
        if dialog.choice == "start":
            self.start_camera()

    def start_camera(self) -> None:
        if not self._model_ready:
            self._pending_camera_start = True
            self._set_toast("模型正在初始化，就绪后将自动开启摄像头")
            return
        self.camera.start()

    def stop_camera(self) -> None:
        self.camera.stop()
        self._set_toast("正在立即停止摄像头…")

    def _on_camera_state(self, active: bool, message: str) -> None:
        self._camera_active = active
        self.camera_pill.set_state(active, message)
        self.start_button.setEnabled(not active and self._model_ready)
        self.stop_button.setEnabled(active)
        self.dashboard_page.set_camera_state(active, message)
        self.recognition_page.set_camera_state(active, message)
        if active:
            self._set_toast("摄像头正在使用 · 点击 Stop Camera 可立即停止")
        else:
            self._set_toast(message)
        if self._pending_enrollment and not active:
            self._pending_enrollment = False
            QTimer.singleShot(120, self._open_enrollment_dialog)

    def _on_model_state(self, ok: bool, message: str) -> None:
        self._model_ready = ok
        self.model_pill.set_state(ok, "模型就绪" if ok else "模型不可用")
        self.start_button.setEnabled(ok and not self._camera_active)
        self.dashboard_page.set_model_state(ok, message)
        self.recognition_page.set_model_state(ok, message)
        if ok and self._pending_camera_start:
            self._pending_camera_start = False
            self.camera.start()
        if not ok and os.environ.get("FACEVAULT_HEADLESS_SMOKE") != "1":
            self._show_error("模型加载失败", message)

    def _on_frame(self, packet) -> None:
        self.dashboard_page.update_packet(packet)
        self.recognition_page.set_packet(packet)

    def _show_error(self, title: str, message: str) -> None:
        logger.warning("用户可见错误：%s | %s", title, message)
        self._set_toast(f"{title}：{message}")
        if os.environ.get("FACEVAULT_HEADLESS_SMOKE") != "1":
            QMessageBox.warning(self, title, message)

    def _set_toast(self, message: str) -> None:
        self.toast_label.setText(message)
        QTimer.singleShot(4500, lambda: self.toast_label.setText(""))

    def refresh_data(self) -> None:
        try:
            people = self.database.list_people()
            history = self.database.list_recognition_history(500)
            counts = self.database.dashboard_counts()
        except (DatabaseError, OSError) as exc:
            logger.exception("刷新本地数据失败")
            self.statusBar().showMessage(f"数据库读取失败：{exc}")
            return
        self.people_page.set_people(people)
        self.history_page.set_records(history)
        self.dashboard_page.set_counts(counts)
        self.dashboard_page.set_history(history)

    def add_person(self) -> None:
        if self._enrollment_dialog is not None:
            return
        self._resume_camera_after_enrollment = self._camera_active
        if self._camera_active:
            self._pending_enrollment = True
            self.switch_page(1)
            self.stop_camera()
        else:
            self._open_enrollment_dialog()

    def _open_enrollment_dialog(self) -> None:
        if self._enrollment_dialog is not None:
            return
        dialog = EnrollmentDialog(self.settings, self)
        self._enrollment_dialog = dialog
        dialog.save_requested.connect(self._save_enrollment)
        try:
            dialog.exec()
        finally:
            self._enrollment_dialog = None
            if self._resume_camera_after_enrollment:
                self._resume_camera_after_enrollment = False
                QTimer.singleShot(250, self.start_camera)

    def _save_enrollment(self, name: str, samples: list[EnrollmentSample]) -> None:
        if self._enrollment_dialog is None:
            return
        try:
            self.database.add_person(
                name=name,
                embeddings=[sample.embedding for sample in samples],
                qualities=[sample.quality for sample in samples],
                model_name="SFace-2021dec",
            )
        except (ValueError, DatabaseError) as exc:
            self._enrollment_dialog.show_save_error(str(exc))
            return
        self.camera.reload_people()
        self.refresh_data()
        self._enrollment_dialog.accept_saved()
        self._set_toast(f"已录入 {name}，仅保存本地人脸特征")

    def rename_person(self, person_id: int) -> None:
        person = self.database.get_person(person_id)
        if person is None:
            self._show_error("人员不存在", "该人员档案可能已被删除。")
            self.refresh_data()
            return
        dialog = PersonNameDialog(
            "修改姓名", "新姓名将用于本地识别结果。", person.name, self
        )
        if dialog.exec() != dialog.Accepted:
            return
        try:
            self.database.update_person_name(person_id, dialog.value())
            self.camera.reload_people()
            self.refresh_data()
            self._set_toast("姓名已更新")
        except (ValueError, DatabaseError) as exc:
            QMessageBox.warning(self, "修改失败", str(exc))

    def delete_person(self, person_id: int) -> None:
        person = self.database.get_person(person_id)
        if person is None:
            self.refresh_data()
            return
        answer = QMessageBox.question(
            self,
            "删除人员",
            f"确定要删除“{person.name}”吗？\n该人员的全部本地人脸特征将一并删除。",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        confirm = DangerConfirmDialog(
            "再次确认删除",
            f"将永久删除 {person.name} 及其 {person.embedding_count} 个本地人脸特征样本。",
            "确认删除",
            self,
        )
        if confirm.exec() != confirm.Accepted:
            return
        try:
            self.database.delete_person(person_id)
            self.camera.reload_people()
            self.refresh_data()
            self._set_toast(f"已删除 {person.name}")
        except (ValueError, DatabaseError) as exc:
            self._show_error("删除失败", str(exc))

    def clear_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "清空识别历史",
            "所有识别日志将从 SQLite 数据库中永久删除，是否继续？",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        confirm = DangerConfirmDialog(
            "再次确认清空历史",
            "此操作不会删除人员档案，但会永久删除全部识别日志。",
            "确认删除",
            self,
        )
        if confirm.exec() != confirm.Accepted:
            return
        try:
            count = self.database.clear_recognition_history()
            self.refresh_data()
            self._set_toast(f"已删除 {count} 条识别日志")
        except (DatabaseError, OSError) as exc:
            self._show_error("清空失败", str(exc))

    def delete_all_people(self) -> None:
        answer = QMessageBox.question(
            self,
            "删除全部人员",
            "这会删除所有人员档案和全部人脸特征，且不可恢复。是否继续？",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        confirm = DangerConfirmDialog(
            "再次确认删除全部人员",
            "所有 Registered People 和 face_embeddings 都会被永久删除。",
            "确认删除",
            self,
        )
        if confirm.exec() != confirm.Accepted:
            return
        try:
            count = self.database.delete_all_people()
            self.camera.reload_people()
            self.refresh_data()
            self._set_toast(f"已删除 {count} 个人员档案")
        except (DatabaseError, OSError) as exc:
            self._show_error("删除失败", str(exc))

    def save_settings(self, values: dict) -> None:
        old_camera_index = self.settings.get("camera_index")
        old_resolution = self.settings.get("resolution")
        old_fps = self.settings.get("fps_limit")
        self.settings.update(**values)
        self._apply_theme()
        self.settings_page.set_data_directory(str(self.settings.data_directory()))
        camera_changed = (
            old_camera_index != values.get("camera_index")
            or old_resolution != values.get("resolution")
            or old_fps != values.get("fps_limit")
        )
        if self._camera_active:
            message = "设置已保存。摄像头相关参数将在下次开启摄像头时生效。"
            if camera_changed:
                message += " 若要立即应用，请先停止再开启摄像头。"
        else:
            message = "设置已保存。"
        self._set_toast(message)
        QMessageBox.information(self, "设置已保存", message)

    def open_data_directory(self) -> None:
        path = self.settings.data_directory()
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                QProcess.startDetached("xdg-open", [str(path)])
        except OSError as exc:
            self._show_error("无法打开目录", str(exc))

    def change_data_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "选择 FaceVault 数据目录", str(self.settings.data_directory())
        )
        if not selected:
            return
        selected_path = Path(selected).resolve()
        if selected_path == self.settings.data_directory().resolve():
            return
        self.settings.update(data_directory=str(selected_path))
        self.settings_page.set_data_directory(str(selected_path))
        answer = QMessageBox.question(
            self,
            "需要重启",
            "新目录已保存。FaceVault 现在重启后会在新目录创建并读取本地数据库。\n是否立即重启？",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._restart_application()

    def reset_settings(self) -> None:
        confirm = DangerConfirmDialog(
            "恢复默认设置",
            "摄像头、识别阈值、主题和数据目录设置将恢复默认；人员档案和历史不会删除。",
            "确认删除",
            self,
        )
        if confirm.exec() != confirm.Accepted:
            return
        self.settings.reset()
        self.settings_page.load_values()
        self._apply_theme()
        self._set_toast("设置已恢复默认，数据目录将在重启后恢复")
        QMessageBox.information(
            self,
            "设置已重置",
            "设置已恢复默认。当前数据库仍保持打开，数据目录变更将在重启后生效。",
        )

    def _apply_theme(self) -> None:
        theme = str(self.settings.get("theme", "dark"))
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_stylesheet(theme))
        if hasattr(self, "settings_page"):
            self.settings_page.activate_for_theme(theme)

    def _restart_application(self) -> None:
        program = sys.executable
        arguments = [] if is_frozen() else [str(Path(sys.argv[0]).resolve())]
        started = QProcess.startDetached(program, arguments)
        if started:
            QApplication.quit()
        else:
            self._show_error(
                "重启失败", "无法自动启动新实例，请手动关闭并重新打开 FaceVault。"
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("FaceVault 正在退出")
        self.refresh_timer.stop()
        self.camera.shutdown()
        super().closeEvent(event)
