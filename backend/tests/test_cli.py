import sqlite3
import stat

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.cli import create_sqlite_backup


def test_sqlite_backup_contains_current_database_and_is_private(tmp_path) -> None:
    database_engine = create_engine("sqlite://", poolclass=StaticPool)
    with database_engine.begin() as connection:
        connection.execute(text("CREATE TABLE backup_check (value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO backup_check (value) VALUES ('saved')"))

    backup_path = create_sqlite_backup(database_engine, tmp_path / "private-backups")

    with sqlite3.connect(backup_path) as backup:
        assert backup.execute("SELECT value FROM backup_check").fetchone() == ("saved",)
    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    database_engine.dispose()


def test_sqlite_backup_rejects_other_database_engines(tmp_path) -> None:
    database_engine = create_engine("postgresql+psycopg://")
    try:
        with pytest.raises(ValueError, match="only available when DATABASE_URL uses SQLite"):
            create_sqlite_backup(database_engine, tmp_path / "private-backups")
    finally:
        database_engine.dispose()