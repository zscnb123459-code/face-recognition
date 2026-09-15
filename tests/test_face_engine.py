"""Model loading smoke test."""

from __future__ import annotations

import numpy as np

from app.recognition import FaceEngine


def test_face_engine_loads_and_detects_blank_frame():
    engine = FaceEngine()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = engine.detect(frame)
    assert faces.shape[0] == 0


def test_sface_extraction_api_is_compatible():
    engine = FaceEngine()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    face = np.array(
        [230, 115, 180, 250, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32
    )
    embedding = engine.extract_embedding(frame, face)
    assert embedding.shape == (1, 128)
    assert abs(engine.compare(embedding, embedding) - 1.0) < 1e-5
