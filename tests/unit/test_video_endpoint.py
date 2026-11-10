from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core.security import require_api_key
from main import app


@pytest.fixture
def client():
    # Use TestClient with bypass on require_api_key dependency for unit testing
    app.dependency_overrides[require_api_key] = lambda: None
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_trigger_generation_with_custom_payload(client):
    payload = {
        "product_title": "Sony WH-1000XM5 Headphones",
        "price": 349.99,
        "image_url": "https://example.com/sony.jpg",
        "voice_persona": "am_adam",
        "aspect_ratio": "16:9",
        "use_llm_script": True,
    }

    mock_task = MagicMock()
    mock_task.id = "mock-task-uuid-1234"

    with patch(
        "api.v1.endpoints.videos.generate_weekly_videos_task.delay",
        return_value=mock_task,
    ) as mock_delay:
        response = client.post("/api/v1/videos/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["task_id"] == "mock-task-uuid-1234"

        # Verify task was called with expected dictionary
        mock_delay.assert_called_once()
        called_args = mock_delay.call_args[0][0]
        assert called_args["product_title"] == "Sony WH-1000XM5 Headphones"
        assert called_args["price"] == 349.99
        assert called_args["image_url"] == "https://example.com/sony.jpg"
        assert called_args["voice_persona"] == "am_adam"
        assert called_args["aspect_ratio"] == "16:9"


def test_trigger_generation_without_payload(client):
    mock_task = MagicMock()
    mock_task.id = "mock-batch-uuid-5678"

    with patch(
        "api.v1.endpoints.videos.generate_weekly_videos_task.delay",
        return_value=mock_task,
    ) as mock_delay:
        response = client.post("/api/v1/videos/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["task_id"] == "mock-batch-uuid-5678"

        mock_delay.assert_called_once_with(None)


def test_trigger_generation_invalid_payload(client):
    invalid_payload = {
        "product_title": "",  # Min length is 1
        "price": -10.0,  # gt 0
        "image_url": "https://example.com/item.jpg",
    }
    response = client.post("/api/v1/videos/generate", json=invalid_payload)
    assert response.status_code == 422
