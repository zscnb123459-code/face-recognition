"""Recognition stabilization tests."""

from __future__ import annotations

from app.models import FaceObservation
from app.recognition import RecognitionStabilizer


def observation(name: str, person_id: int | None, similarity: float) -> FaceObservation:
    return FaceObservation(
        bbox=(10, 10, 100, 100),
        person_id=person_id,
        name=name,
        similarity=similarity,
        recognized=person_id is not None,
        stable=False,
        quality_score=0.9,
    )


def test_identity_requires_consecutive_consistent_frames():
    stabilizer = RecognitionStabilizer(stable_frames=3)
    outputs = [stabilizer.update([observation("Cheng", 1, 0.8)])[0] for _ in range(3)]
    assert outputs[0].name == "确认中"
    assert outputs[1].name == "确认中"
    assert outputs[2].stable is True
    assert outputs[2].name == "Cheng"
    assert abs(outputs[2].similarity - 0.8) < 1e-6


def test_identity_change_resets_stability():
    stabilizer = RecognitionStabilizer(stable_frames=2)
    stabilizer.update([observation("Cheng", 1, 0.8)])
    stable = stabilizer.update([observation("Cheng", 1, 0.8)])[0]
    assert stable.stable is True
    changing = stabilizer.update([observation("Unknown", None, 0.1)])[0]
    assert changing.stable is False
    unknown = stabilizer.update([observation("Unknown", None, 0.1)])[0]
    assert unknown.stable is True
    assert unknown.name == "Unknown"
