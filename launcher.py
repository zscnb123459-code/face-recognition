"""Small Windows launcher for the portable FaceVault runtime.

The actual Qt runtime is copied to an ASCII-only path before launch. This
works around native Windows libraries that fail when loaded from a Chinese
folder, while keeping FaceVaultData next to the visible portable EXE.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

APP_VERSION = "1.0.0"


def message(title: str, text: str, error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except (AttributeError, OSError):
        pass


def source_root() -> Path:
    return Path(sys.executable).resolve().parent


def runtime_parent() -> Path:
    public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    if any(ord(char) >= 128 for char in str(public)):
        public = Path(r"C:\Users\Public")
    return public / "FaceVaultRuntime" / APP_VERSION


def read_token(path: Path) -> str:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return ""


def prepare_runtime(source: Path, target: Path) -> Path:
    source_exe = source / "FaceVault.exe"
    if not source_exe.exists():
        raise FileNotFoundError(f"缺少运行文件：{source_exe}")
    source_token = read_token(source / "runtime.token")
    target_token = read_token(target / "runtime.token")
    if target.exists() and source_token and source_token == target_token:
        return target / "FaceVault.exe"

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp = parent / f"runtime_{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, temp)
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return target / "FaceVault.exe"


def main() -> int:
    root = source_root()
    runtime = root / "runtime"
    target = runtime_parent()
    try:
        source_token = read_token(runtime / "runtime.token")
        if (
            read_token(target / "runtime.token") != source_token
            and os.environ.get("FACEVAULT_LAUNCHER_NO_PROMPT") != "1"
        ):
            message(
                "FaceVault",
                "首次启动或程序已更新，正在准备本地运行环境。\n"
                "请稍候，准备完成后会自动打开 FaceVault。",
            )
        executable = prepare_runtime(runtime, target)
        environment = os.environ.copy()
        environment["FACEVAULT_PORTABLE_ROOT"] = str(root)
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        subprocess.Popen(
            [str(executable)],
            cwd=str(root),
            env=environment,
            close_fds=True,
            creationflags=creation_flags,
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - show a Windows message for any startup failure
        message("FaceVault 启动失败", f"无法准备或启动 FaceVault：\n{exc}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
