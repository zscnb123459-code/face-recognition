"""Database behavior tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.database import Database


def test_people_embeddings_history_crud(tmp_path):
    database = Database(tmp_path / "facevault.db")
    embedding = np.ones((1, 128), dtype=np.float32)
    person_id = database.add_person("Cheng", [embedding], "SFace-2021dec", [0.9])
    people = database.list_people()
    assert len(people) == 1
    assert people[0].id == person_id
    assert people[0].embedding_count == 1

    known = database.get_known_embeddings()
    assert len(known) == 1
    assert known[0][0] == person_id
    assert np.allclose(known[0][2], embedding)

    database.update_person_name(person_id, "Cheng Li")
    assert database.get_person(person_id).name == "Cheng Li"

    history_id = database.add_recognition_history(person_id, "Cheng Li", 0.82, True)
    assert history_id > 0
    history = database.list_recognition_history()
    assert history[0].matched is True
    assert history[0].similarity == pytest.approx(0.82)

    database.delete_person(person_id)
    assert database.get_person(person_id) is None
    history_after = database.list_recognition_history()
    assert history_after[0].person_id is None
    assert history_after[0].label == "Cheng Li"


def test_clear_and_dashboard_counts(tmp_path):
    database = Database(tmp_path / "facevault.db")
    database.add_person("A", [np.ones(128, dtype=np.float32)], "SFace-2021dec", [1.0])
    database.add_recognition_history(None, "Unknown", 0.12, False)
    counts = database.dashboard_counts()
    assert counts["people"] == 1
    assert counts["today_unknown"] == 1
    assert database.clear_recognition_history() == 1
    assert database.dashboard_counts()["today_unknown"] == 0


def test_duplicate_name_rolls_back(tmp_path):
    database = Database(tmp_path / "facevault.db")
    database.add_person("A", [np.ones(128, dtype=np.float32)], "model", [1.0])
    with pytest.raises(ValueError):
        database.add_person("a", [np.ones(128, dtype=np.float32)], "model", [1.0])
    assert len(database.list_people()) == 1
    assert database.dashboard_counts()["embeddings"] == 1
