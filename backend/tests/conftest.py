from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import clear_settings_cache
from app.database import Base
from app.main import create_app


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-that-is-at-least-32-characters")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080")
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def client(configured: None) -> Iterator[TestClient]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    from app.models import AdminUser, Branch
    from app.security import hash_password

    with Session(test_engine) as db:
        bootstrap = AdminUser(
            email="test-branch-bootstrap@example.org",
            display_name="Test Branch Bootstrap",
            role="admin",
            password_hash=hash_password("long-test-password-2026"),
        )
        db.add(bootstrap)
        db.flush()
        db.add(Branch(name="Test Local Branch", location="Test", created_by_id=bootstrap.id))
        db.commit()
    test_app = create_app(test_engine)
    test_app.state.database_engine = test_engine
    with TestClient(test_app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def provision_user(client: TestClient, email: str, role: str = "admin") -> str:
    from app.models import AdminUser, Branch
    from app.security import hash_password

    with Session(client.app.state.database_engine) as db:
        user = AdminUser(email=email, display_name="Test staff", role=role, password_hash=hash_password("long-test-password-2026"))
        db.add(user)
        db.flush()
        branch = db.scalar(select(Branch).where(Branch.is_active.is_(True)).order_by(Branch.id))
        assert branch is not None
        user.branch_id = branch.id
        db.commit()
    response = client.post("/api/v1/auth/token", json={"email": email, "password": "long-test-password-2026"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]