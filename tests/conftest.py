import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from uuid import uuid4

from main import app
from database.session import get_session


@pytest.fixture
def client():
    # Create a unique SQLite database for every test
    database_url = f"sqlite:///./test_{uuid4().hex}.db"

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "role": "staff",
    }