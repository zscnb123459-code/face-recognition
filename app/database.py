"""Atomic, parameterized SQLite persistence for FaceVault."""

from __future__ import annotations

import shutil
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np

from app.models import HistoryRecord, PersonRecord
from app.utils.image_utils import blob_to_embedding, embedding_to_blob
from app.utils.logging_setup import get_logger

logger = get_logger("database")


class DatabaseError(RuntimeError):
    pass


class Database:
    """Small database facade with one connection per operation.

    A separate short-lived connection keeps the class safe when called from the
    camera thread, enrollment thread and Qt main thread.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self._initialize_or_recover()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=8.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 8000")
            yield connection
        finally:
            connection.close()

    def _initialize_or_recover(self) -> None:
        with self._schema_lock:
            try:
                with self.connection() as connection:
                    integrity = connection.execute("PRAGMA quick_check").fetchone()
                    if not integrity or integrity[0] != "ok":
                        raise sqlite3.DatabaseError("SQLite quick_check failed")
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS people (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS face_embeddings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            person_id INTEGER NOT NULL,
                            embedding BLOB NOT NULL,
                            model_name TEXT NOT NULL,
                            quality REAL NOT NULL DEFAULT 0,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
                        );

                        CREATE TABLE IF NOT EXISTS recognition_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            person_id INTEGER NULL,
                            label TEXT NOT NULL,
                            similarity REAL NULL,
                            matched INTEGER NOT NULL DEFAULT 0,
                            camera_status TEXT NOT NULL DEFAULT 'camera_on',
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
                        );

                        CREATE INDEX IF NOT EXISTS idx_embeddings_person
                            ON face_embeddings(person_id);
                        CREATE INDEX IF NOT EXISTS idx_history_created
                            ON recognition_history(created_at DESC);
                        CREATE INDEX IF NOT EXISTS idx_history_person
                            ON recognition_history(person_id);
                        """
                    )
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute("PRAGMA user_version = 1")
                    connection.commit()
                logger.info("SQLite 数据库已初始化")
            except sqlite3.DatabaseError as exc:
                logger.error("数据库损坏或无法打开，将隔离并重建：%s", exc)
                self._quarantine_corrupt_database()
                try:
                    with self.connection() as connection:
                        connection.executescript(self._schema_sql())
                        connection.execute("PRAGMA journal_mode = WAL")
                        connection.commit()
                    logger.info("已创建新的 SQLite 数据库")
                except sqlite3.DatabaseError as second_exc:
                    raise DatabaseError(
                        f"无法初始化数据库：{second_exc}"
                    ) from second_exc

    @staticmethod
    def _schema_sql() -> str:
        return """
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS face_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            model_name TEXT NOT NULL,
            quality REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS recognition_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NULL,
            label TEXT NOT NULL,
            similarity REAL NULL,
            matched INTEGER NOT NULL DEFAULT 0,
            camera_status TEXT NOT NULL DEFAULT 'camera_on',
            created_at TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_embeddings_person ON face_embeddings(person_id);
        CREATE INDEX IF NOT EXISTS idx_history_created ON recognition_history(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_history_person ON recognition_history(person_id);
        """

    def _quarantine_corrupt_database(self) -> None:
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        for suffix in ("", "-wal", "-shm"):
            source = Path(f"{self.path}{suffix}")
            if not source.exists():
                continue
            target = source.with_name(f"{source.name}.corrupt_{stamp}")
            try:
                shutil.move(str(source), str(target))
            except OSError:
                logger.exception("无法隔离损坏的数据库文件：%s", source)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def add_person(
        self,
        name: str,
        embeddings: Sequence[np.ndarray],
        model_name: str,
        qualities: Sequence[float] | None = None,
    ) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("姓名不能为空")
        vectors = [
            np.asarray(item, dtype=np.float32).reshape(-1) for item in embeddings
        ]
        if not vectors:
            raise ValueError("至少需要一个人脸特征样本")
        quality_values = list(qualities or [0.0] * len(vectors))
        if len(quality_values) != len(vectors):
            raise ValueError("样本质量数据数量不一致")
        now = self._utc_now()
        try:
            with self.connection() as connection:
                cursor = connection.execute(
                    "INSERT INTO people(name, created_at, updated_at) VALUES (?, ?, ?)",
                    (clean_name, now, now),
                )
                person_id = int(cursor.lastrowid)
                connection.executemany(
                    """
                    INSERT INTO face_embeddings(person_id, embedding, model_name, quality, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            person_id,
                            embedding_to_blob(vector),
                            model_name,
                            float(quality),
                            now,
                        )
                        for vector, quality in zip(vectors, quality_values)
                    ],
                )
                connection.commit()
            logger.info("已添加人员档案，样本数=%d", len(vectors))
            return person_id
        except sqlite3.IntegrityError as exc:
            raise ValueError("该姓名已存在，请使用其他名称") from exc
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"保存人员档案失败：{exc}") from exc

    def update_person_name(self, person_id: int, name: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("姓名不能为空")
        try:
            with self.connection() as connection:
                cursor = connection.execute(
                    "UPDATE people SET name = ?, updated_at = ? WHERE id = ?",
                    (clean_name, self._utc_now(), person_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("人员不存在")
                connection.commit()
            logger.info("已修改人员姓名，person_id=%s", person_id)
        except sqlite3.IntegrityError as exc:
            raise ValueError("该姓名已存在，请使用其他名称") from exc

    def delete_person(self, person_id: int) -> None:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM people WHERE id = ?", (person_id,))
            connection.commit()
        if cursor.rowcount == 0:
            raise ValueError("人员不存在")
        logger.info("已删除人员档案，person_id=%s", person_id)

    def delete_all_people(self) -> int:
        with self.connection() as connection:
            count = int(connection.execute("SELECT COUNT(*) FROM people").fetchone()[0])
            connection.execute("DELETE FROM people")
            connection.commit()
        logger.warning("已删除全部人员档案，数量=%d", count)
        return count

    def get_person(self, person_id: int) -> PersonRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT p.id, p.name, p.created_at, p.updated_at,
                       COUNT(e.id) AS embedding_count
                FROM people p
                LEFT JOIN face_embeddings e ON e.person_id = p.id
                WHERE p.id = ?
                GROUP BY p.id
                """,
                (person_id,),
            ).fetchone()
        return self._row_to_person(row) if row else None

    def list_people(self, search: str = "") -> list[PersonRecord]:
        query = """
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(e.id) AS embedding_count
            FROM people p
            LEFT JOIN face_embeddings e ON e.person_id = p.id
        """
        params: list[object] = []
        if search.strip():
            query += " WHERE p.name LIKE ? ESCAPE '\\'"
            escaped = (
                search.strip()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            params.append(f"%{escaped}%")
        query += " GROUP BY p.id ORDER BY p.name COLLATE NOCASE"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_person(row) for row in rows]

    @staticmethod
    def _row_to_person(row: sqlite3.Row) -> PersonRecord:
        return PersonRecord(
            id=int(row["id"]),
            name=str(row["name"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            embedding_count=int(row["embedding_count"]),
        )

    def get_known_embeddings(self) -> list[tuple[int, str, np.ndarray]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT e.person_id, p.name, e.embedding
                FROM face_embeddings e
                JOIN people p ON p.id = e.person_id
                ORDER BY e.person_id, e.id
                """
            ).fetchall()
        result: list[tuple[int, str, np.ndarray]] = []
        for row in rows:
            try:
                result.append(
                    (
                        int(row["person_id"]),
                        str(row["name"]),
                        blob_to_embedding(bytes(row["embedding"])),
                    )
                )
            except (ValueError, TypeError):
                logger.warning("跳过不可读取的人脸特征，person_id=%s", row["person_id"])
        return result

    def add_recognition_history(
        self,
        person_id: int | None,
        label: str,
        similarity: float | None,
        matched: bool,
        camera_status: str = "camera_on",
    ) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO recognition_history(
                    person_id, label, similarity, matched, camera_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    label,
                    similarity,
                    1 if matched else 0,
                    camera_status,
                    self._utc_now(),
                ),
            )
            connection.commit()
        return int(cursor.lastrowid)

    def list_recognition_history(self, limit: int = 500) -> list[HistoryRecord]:
        safe_limit = max(1, min(int(limit), 5000))
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, person_id, label, similarity, matched, camera_status, created_at
                FROM recognition_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [
            HistoryRecord(
                id=int(row["id"]),
                person_id=int(row["person_id"])
                if row["person_id"] is not None
                else None,
                label=str(row["label"]),
                similarity=float(row["similarity"])
                if row["similarity"] is not None
                else None,
                matched=bool(row["matched"]),
                camera_status=str(row["camera_status"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def clear_recognition_history(self) -> int:
        with self.connection() as connection:
            count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM recognition_history"
                ).fetchone()[0]
            )
            connection.execute("DELETE FROM recognition_history")
            connection.commit()
        logger.warning("已清空识别历史，数量=%d", count)
        return count

    def dashboard_counts(self) -> dict[str, int]:
        local_prefix = datetime.now().astimezone().date().isoformat()
        with self.connection() as connection:
            people = int(
                connection.execute("SELECT COUNT(*) FROM people").fetchone()[0]
            )
            embeddings = int(
                connection.execute("SELECT COUNT(*) FROM face_embeddings").fetchone()[0]
            )
            today_matched = int(
                connection.execute(
                    "SELECT COUNT(*) FROM recognition_history WHERE matched = 1 AND created_at LIKE ?",
                    (f"{local_prefix}%",),
                ).fetchone()[0]
            )
            today_unknown = int(
                connection.execute(
                    "SELECT COUNT(*) FROM recognition_history WHERE matched = 0 AND created_at LIKE ?",
                    (f"{local_prefix}%",),
                ).fetchone()[0]
            )
        return {
            "people": people,
            "embeddings": embeddings,
            "today_matched": today_matched,
            "today_unknown": today_unknown,
        }

    def get_popular_people(self, limit: int = 5) -> list[tuple[str, int]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT label, COUNT(*) AS count
                FROM recognition_history
                WHERE matched = 1
                GROUP BY person_id, label
                ORDER BY count DESC, label COLLATE NOCASE
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()
        return [(str(row["label"]), int(row["count"])) for row in rows]
