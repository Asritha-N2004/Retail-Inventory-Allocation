import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(temp.name) / "test.db").replace(
    "\\", "/"
)
os.environ["JWT_SECRET"] = "test-secret-at-least-thirty-two-characters"
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    from app.database import engine

    engine.dispose()
    temp.cleanup()


@pytest.fixture(scope="session")
def auth(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "RetailDemo!2026"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}
