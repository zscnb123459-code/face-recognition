"""Image and embedding helpers."""

from __future__ import annotations

import math

import cv2
import numpy as np


def embedding_to_blob(embedding: np.ndarray) -> bytes:
    vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if vector.size == 0:
        raise ValueError("人脸特征不能为空")
    return vector.tobytes()


def blob_to_embedding(blob: bytes, expected_size: int | None = None) -> np.ndarray:
    vector = np.frombuffer(blob, dtype=np.float32).copy()
    if expected_size is not None and vector.size != expected_size:
        raise ValueError(f"人脸特征长度异常：{vector.size}，预期 {expected_size}")
    return vector.reshape(1, -1)


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=np.float32).reshape(-1)
    b = np.asarray(right, dtype=np.float32).reshape(-1)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator <= 1e-12:
        return -1.0
    return float(np.dot(a, b) / denominator)


def bbox_iou(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def enlarged_roi(
    frame: np.ndarray, bbox: tuple[int, int, int, int], margin: float = 0.12
) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, w, h = bbox
    mx, my = int(w * margin), int(h * margin)
    x1, y1 = max(0, x - mx), max(0, y - my)
    x2, y2 = min(width, x + w + mx), min(height, y + h + my)
    return frame[y1:y2, x1:x2]


def assess_face_quality(
    frame: np.ndarray,
    bbox: tuple[int, int, int, int],
    min_face_size: int,
    detection_score: float = 1.0,
) -> tuple[float, str]:
    """Return a bounded quality score and a user-facing issue message."""

    _x, _y, width, height = bbox
    if width <= 0 or height <= 0:
        return 0.0, "无法读取人脸区域"

    if min(width, height) < min_face_size:
        return 0.12, "请靠近摄像头，让人脸更大"

    roi = enlarged_roi(frame, bbox)
    if roi.size == 0:
        return 0.0, "无法读取人脸区域"

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if brightness < 45:
        return 0.25, "光线太暗，请增加正面照明"
    if brightness > 225:
        return 0.35, "画面过亮，请避开强光直射"
    if contrast < 22:
        return 0.42, "画面对比度偏低，请调整光线"
    if blur_score < 28:
        return 0.48, "画面偏模糊，请保持稳定"

    size_score = min(1.0, min(width, height) / max(min_face_size * 1.8, 1))
    exposure_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0)
    sharpness_score = min(1.0, math.log10(max(blur_score, 1.0)) / 2.7)
    quality = 0.45 * size_score + 0.25 * exposure_score + 0.30 * sharpness_score
    quality *= 0.6 + 0.4 * max(0.0, min(1.0, detection_score))
    return float(max(0.0, min(1.0, quality))), ""


def numpy_to_qimage(frame: np.ndarray):
    """Convert an OpenCV BGR image to a detached QImage."""

    from PySide6.QtGui import QImage

    if frame.ndim == 2:
        image = QImage(
            frame.data,
            frame.shape[1],
            frame.shape[0],
            frame.strides[0],
            QImage.Format_Grayscale8,
        )
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888
        )
    return image.copy()
