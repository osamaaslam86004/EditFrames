import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from core.config import get_settings

logger = logging.getLogger(__name__)

TELEMETRY_CHANNEL = "editframes_telemetry"


class ConnectionManager:
    """
    Manages WebSocket client connections and synchronizes telemetry events
    across multi-container FastAPI instances using a Redis Pub/Sub backplane.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None
        self._is_running: bool = False

    async def get_redis(self) -> aioredis.Redis | None:
        """Lazily initialize or return the async Redis client."""
        if self._redis is None:
            try:
                settings = get_settings()
                self._redis = aioredis.from_url(
                    settings.redis.async_url,
                    decode_responses=True,
                    socket_connect_timeout=settings.redis.socket_connect_timeout,
                    socket_timeout=settings.redis.socket_timeout,
                )
            except Exception as exc:
                logger.warning(
                    "Could not initialize Redis client for backplane: %s", exc
                )
                return None
        return self._redis

    async def start(self) -> None:
        """Starts the Redis Pub/Sub backplane listener background task."""
        if self._is_running:
            return

        self._is_running = True
        try:
            client = await self.get_redis()
            if client is not None:
                self._pubsub = client.pubsub()
                await self._pubsub.subscribe(TELEMETRY_CHANNEL)
                self._listener_task = asyncio.create_task(self._listen_loop())
                logger.info(
                    "Redis Pub/Sub telemetry listener subscribed to '%s'",
                    TELEMETRY_CHANNEL,
                )
        except Exception as exc:
            logger.warning("Failed starting Redis Pub/Sub backplane: %s", exc)

    async def stop(self) -> None:
        """Stops the Redis Pub/Sub backplane listener and unsubscribes."""
        self._is_running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(TELEMETRY_CHANNEL)
                await self._pubsub.close()
            except Exception as exc:
                logger.debug("Error closing Redis pubsub: %s", exc)
            self._pubsub = None

        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception as exc:
                logger.debug("Error closing Redis client: %s", exc)
            self._redis = None

    async def _listen_loop(self) -> None:
        """Continuously reads messages from Redis channel and distributes to local WebSockets."""
        while self._is_running and self._pubsub is not None:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message.get("type") == "message":
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    if data:
                        await self._send_to_local(str(data))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Error in Redis Pub/Sub listener loop: %s", exc)
                await asyncio.sleep(1.0)

    async def _send_to_local(self, message: str) -> None:
        """Delivers a text message to all locally connected WebSocket clients."""
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts a new WebSocket connection and adds it to the active pool."""
        await websocket.accept()
        self.active_connections.append(websocket)
        # Ensure backplane listener is running
        if self._listener_task is None or self._listener_task.done():
            await self.start()

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a disconnected WebSocket from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str) -> None:
        """
        Publishes telemetry events to the Redis channel 'editframes_telemetry'
        so all instances can broadcast the event to their connected clients.
        Also delivers locally as a fallback or immediate sync.
        """
        published = False
        try:
            client = await self.get_redis()
            if client is not None:
                await client.publish(TELEMETRY_CHANNEL, message)
                published = True
        except Exception as exc:
            logger.warning(
                "Could not publish telemetry to Redis backplane '%s': %s",
                TELEMETRY_CHANNEL,
                exc,
            )

        # Fallback to local delivery if pubsub is not running or redis is offline
        if not published or self._listener_task is None or self._listener_task.done():
            await self._send_to_local(message)


manager = ConnectionManager()
