from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from core.security import require_api_key
from db.models.videos_model import VideoJob
from db.session import get_db_session
from main import app


@pytest.fixture
def client_with_db():
    mock_db = AsyncMock()

    app.dependency_overrides[require_api_key] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: mock_db

    with TestClient(app) as c:
        yield c, mock_db

    app.dependency_overrides.clear()


def test_get_job_status_found(client_with_db):
    client, mock_db = client_with_db

    fake_job = VideoJob(
        id="job-uuid-12345",
        product_title="Wireless Earbuds",
        status="completed",
        output_url="https://my-bucket.s3.amazonaws.com/videos/product_12345.mp4",
        error_message=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_job
    mock_db.execute.return_value = mock_result

    response = client.get("/api/v1/videos/jobs/job-uuid-12345")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "job-uuid-12345"
    assert data["product_title"] == "Wireless Earbuds"
    assert data["status"] == "completed"
    assert (
        data["output_url"]
        == "https://my-bucket.s3.amazonaws.com/videos/product_12345.mp4"
    )
    assert data["error_message"] is None


def test_get_job_status_not_found(client_with_db):
    client, mock_db = client_with_db

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    response = client.get("/api/v1/videos/jobs/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_legacy_get_job_status_found(client_with_db):
    client, mock_db = client_with_db

    fake_job = VideoJob(
        id="job-uuid-legacy",
        product_title="Legacy Product",
        status="processing",
        output_url=None,
        error_message=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_job
    mock_db.execute.return_value = mock_result

    response = client.get("/api/videos/jobs/job-uuid-legacy")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "job-uuid-legacy"
    assert data["status"] == "processing"
