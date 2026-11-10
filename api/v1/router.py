from fastapi import APIRouter

from api.v1.endpoints import health, progress, videos

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(videos.router)
api_router.include_router(videos.legacy_router)

ws_router = APIRouter()
ws_router.include_router(progress.router)
