import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client):
    def current_user():
        return {
            "id": "00000000-0000-0000-0000-000000000001",
            "email": "user@example.com",
            "metadata": {},
            "access_token": "test-token",
        }

    app.dependency_overrides[get_current_user] = current_user
    return client
