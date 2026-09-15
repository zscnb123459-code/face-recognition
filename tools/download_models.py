"""Download the two OpenCV Zoo models used by FaceVault.

This script is only for developers/installers. The application itself never
downloads models or opens a network connection.
"""

from __future__ import annotations

import hashlib
import sys
import time
import urllib.request
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.recognition import _ascii_model_path

MODEL_DIR = ROOT / "resources" / "models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "size": 232589,
        "sha256": "8F2383E4DD3CFBB4553EA8718107FC0423210DC964F9F4280604804ED2552FA4",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "size": 38696353,
        "sha256": "0BA9FBFA01B5270C96627C4EF784DA859931E02F04419C829E83484087C34E79",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(meta: dict, target: Path) -> None:
    temp = target.with_suffix(target.suffix + ".part")
    for attempt in range(1, 7):
        try:
            print(f"下载 {target.name}（第 {attempt}/6 次）…")
            request = urllib.request.Request(
                meta["url"], headers={"User-Agent": "FaceVault-Model-Downloader/1.0"}
            )
            with (
                urllib.request.urlopen(request, timeout=30) as response,
                temp.open("wb") as output,
            ):
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            if temp.stat().st_size != meta["size"]:
                raise OSError(f"文件大小不正确：{temp.stat().st_size}")
            temp.replace(target)
            return
        except Exception as exc:
            print(f"下载失败：{exc}")
            temp.unlink(missing_ok=True)
            if attempt == 6:
                raise
            time.sleep(2 * attempt)


def verify(path: Path, meta: dict) -> None:
    if path.stat().st_size != meta["size"]:
        raise RuntimeError(f"{path.name} 大小不正确")
    if meta["sha256"]:
        actual = sha256(path)
        if actual.lower() != meta["sha256"].lower():
            raise RuntimeError(f"{path.name} SHA256 校验失败：{actual}")
    print(f"模型可用：{path.name} ({path.stat().st_size} bytes)")


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, meta in MODELS.items():
        target = MODEL_DIR / name
        if not target.exists() or target.stat().st_size != meta["size"]:
            download(meta, target)
        verify(target, meta)
    detector_path = _ascii_model_path(MODEL_DIR / "face_detection_yunet_2023mar.onnx")
    recognizer_path = _ascii_model_path(
        MODEL_DIR / "face_recognition_sface_2021dec.onnx"
    )
    cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320))
    cv2.FaceRecognizerSF.create(str(recognizer_path), "")
    print("OpenCV 官方模型加载验证通过。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - command-line installer boundary
        print(f"模型安装失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
