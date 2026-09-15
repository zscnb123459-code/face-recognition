# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).resolve()
icon = root / 'resources' / 'branding' / 'facevault.ico'
version_file = root / 'build_version_info.txt'

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'resources'), 'resources')],
    hiddenimports=['cv2', 'numpy', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas'],
    noarchive=False,
    optimize=1,
)
# Do not bundle ICU DLLs from toolchains on PATH. Windows supplies the
# ABI-compatible system ICU forwarders expected by Qt on Windows.
a.binaries = [
    entry for entry in a.binaries
    if not (Path(entry[0]).name.lower().startswith('icu') and Path(entry[0]).suffix.lower() == '.dll')
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FaceVault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
    version=str(version_file),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FaceVault',
)
