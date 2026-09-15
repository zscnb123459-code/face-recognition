"""Settings persistence tests."""

from __future__ import annotations

from app.services.settings_service import SettingsService


def test_settings_are_validated_and_persisted(tmp_path):
    config = tmp_path / "FaceVault.config.json"
    settings = SettingsService(config)
    settings.update(
        recognition_threshold=0.55,
        stable_frames=6,
        camera_index=2,
        resolution="1920x1080",
        theme="light",
        data_directory=str(tmp_path / "data"),
    )
    loaded = SettingsService(config)
    assert loaded.get("recognition_threshold") == 0.55
    assert loaded.get("stable_frames") == 6
    assert loaded.get("camera_index") == 2
    assert loaded.get("theme") == "light"
    assert loaded.data_directory() == (tmp_path / "data").resolve()


def test_invalid_values_fall_back(tmp_path):
    config = tmp_path / "FaceVault.config.json"
    settings = SettingsService(config)
    settings.update(recognition_threshold=9.0, stable_frames=-2, resolution="bad")
    assert settings.get("recognition_threshold") == 0.80
    assert settings.get("stable_frames") == 2
    assert settings.get("resolution") == "1280x720"
