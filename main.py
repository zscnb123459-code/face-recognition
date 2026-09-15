"""FaceVault portable desktop application entry point."""

from __future__ import annotations

import ctypes
import multiprocessing
import os
import sys
import traceback

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.paths import APP_NAME, APP_VERSION, ORGANIZATION_NAME, resource_path
from app.services.settings_service import SettingsService
from app.ui.main_window import MainWindow
from app.utils.logging_setup import configure_logging


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(  # type: ignore[attr-defined]
            f"{ORGANIZATION_NAME}.{APP_NAME}.{APP_VERSION}"
        )
    except (AttributeError, OSError):
        pass


def _install_exception_hook(logger) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        details = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        logger.error("未捕获异常\n%s", details)
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None,
                "FaceVault 发生错误",
                "程序遇到未预期错误，但已尝试安全退出。\n\n"
                f"{exc_value}\n\n详细信息已写入本地日志。",
            )

    sys.excepthook = handle_exception


def main() -> int:
    multiprocessing.freeze_support()
    _set_windows_app_id()

    settings = SettingsService()
    data_dir = settings.data_directory()
    logger = configure_logging(data_dir)
    _install_exception_hook(logger)
    logger.info("FaceVault %s 启动，数据目录=%s", APP_VERSION, data_dir)

    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setApplicationVersion(APP_VERSION)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = resource_path("branding", "facevault.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setQuitOnLastWindowClosed(True)

    try:
        window = MainWindow(settings)
        window.show()
        smoke_exit_ms = os.environ.get("FACEVAULT_SMOKE_EXIT_MS")
        if smoke_exit_ms:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(max(500, int(smoke_exit_ms)), app.quit)
        return app.exec()
    except Exception:
        logger.exception("FaceVault 启动失败")
        QMessageBox.critical(
            None, "FaceVault 启动失败", "程序无法启动，详细错误已写入本地日志。"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
