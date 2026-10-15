import argparse
import getpass
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, SessionLocal, engine
from app.models import AdminUser
from app.security import hash_password


def create_sqlite_backup(database_engine: Engine, output_dir: Path) -> Path:
    if database_engine.dialect.name != "sqlite":
        raise ValueError("SQLite backup is only available when DATABASE_URL uses SQLite")

    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with tempfile.NamedTemporaryFile(
        prefix=f"church-{timestamp}-",
        suffix=".sqlite3",
        dir=output_dir,
        delete=False,
    ) as backup_file:
        backup_path = Path(backup_file.name)

    source = database_engine.raw_connection()
    target = None
    try:
        target = sqlite3.connect(backup_path)
        source.driver_connection.backup(target)
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    finally:
        if target is not None:
            target.close()
        source.close()
    return backup_path


def create_admin(args: argparse.Namespace) -> int:
    email = args.email.strip().lower()
    if "@" not in email:
        print("Enter a valid email address.", file=sys.stderr)
        return 2

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(AdminUser.id).where(AdminUser.email == email)):
            print("An account with that email already exists.", file=sys.stderr)
            return 1

        if args.password_stdin:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = getpass.getpass("New password (minimum 14 characters): ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                print("Passwords do not match.", file=sys.stderr)
                return 2
        if len(password) < 14:
            print("Password must be at least 14 characters.", file=sys.stderr)
            return 2

        user = AdminUser(
            email=email,
            display_name=args.name.strip(),
            role=args.role,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
    print(f"Created {args.role} account for {email}.")
    return 0


def backup_database(args: argparse.Namespace) -> int:
    try:
        backup_path = create_sqlite_backup(engine, Path(args.output_dir).expanduser())
    except (OSError, sqlite3.Error, SQLAlchemyError, ValueError) as exc:
        print(f"Could not create database backup: {exc}", file=sys.stderr)
        return 1
    print(f"Created database backup at {backup_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Private church platform administration")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="Provision a staff account; there is no public registration")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="Church Administrator")
    create.add_argument("--role", choices=("admin", "editor", "pastor", "treasurer"), default="admin")
    create.add_argument("--password-stdin", action="store_true")
    create.set_defaults(handler=create_admin)
    backup = commands.add_parser("backup-db", help="Create a private SQLite database backup")
    backup.add_argument(
        "--output-dir",
        default=str(Path.home() / ".local" / "state" / "bwala" / "backups"),
    )
    backup.set_defaults(handler=backup_database)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())