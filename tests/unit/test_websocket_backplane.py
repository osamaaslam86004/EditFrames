from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.websocket import TELEMETRY_CHANNEL, ConnectionManager


@pytest.mark.asyncio
async def test_websocket_manager_connect_disconnect():
    manager = ConnectionManager()
    mock_ws = AsyncMock()

    # Mock start so it doesn't try to connect to real Redis
    with patch.object(manager, "start", new_callable=AsyncMock) as mock_start:
        await manager.connect(mock_ws)
        mock_ws.accept.assert_called_once()
        assert mock_ws in manager.active_connections
        mock_start.assert_called_once()

    manager.disconnect(mock_ws)
    assert mock_ws not in manager.active_connections


@pytest.mark.asyncio
async def test_websocket_broadcast_publishes_to_redis():
    manager = ConnectionManager()
    mock_redis = AsyncMock()

    with patch.object(manager, "get_redis", return_value=mock_redis):
        # Listener task is running
        manager._listener_task = MagicMock()
        manager._listener_task.done.return_value = False

        await manager.broadcast("Video rendering progress 50%")

        mock_redis.publish.assert_called_once_with(
            TELEMETRY_CHANNEL, "Video rendering progress 50%"
        )


@pytest.mark.asyncio
async def test_websocket_broadcast_fallback_local():
    manager = ConnectionManager()
    mock_ws = AsyncMock()
    manager.active_connections.append(mock_ws)

    # When Redis publish fails, should fall back to local delivery
    with patch.object(manager, "get_redis", return_value=None):
        await manager.broadcast("Offline local broadcast")
        mock_ws.send_text.assert_called_once_with("Offline local broadcast")


@pytest.mark.asyncio
async def test_websocket_listener_distributes_to_local_clients():
    manager = ConnectionManager()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    manager.active_connections.extend([mock_ws1, mock_ws2])

    await manager._send_to_local("Test telemetry message")

    mock_ws1.send_text.assert_called_once_with("Test telemetry message")
    mock_ws2.send_text.assert_called_once_with("Test telemetry message")
