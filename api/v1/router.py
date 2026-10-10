from fastapi import APIRouter

from api.v1.endpoints import health, videos, progress

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(videos.router)

ws_router = APIRouter()
ws_router.include_router(progress.router)
