from fastapi import APIRouter, status
from sqlalchemy import text

from core.config import get_settings
from core.cache import get_redis_client

from db.session import engine

router = APIRouter(tags=["health"])

settings = get_settings()


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, str]:

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    client = get_redis_client(socket_connect_timeout=2, socket_timeout=2)

    try:
        await client.ping()
    finally:
        await client.aclose()
    return {"status": "ready", "database": "ok", "redis": "ok"}
