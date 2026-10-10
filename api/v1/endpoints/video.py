import asyncio
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.config import get_settings
from workers.tasks import generate_weekly_videos_task

router = APIRouter(
    prefix="/api/v1/videos",
    tags=["Videos"],
    dependencies=[Depends(require_api_key)],
)

settings = get_settings()

VIDEOS_DIR = settings.videos_dir


@router.post("/generate")
async def trigger_generation():
    asyncio.create_task(generate_weekly_videos_task())
    return {"status": "started", "message": "KittenTTS generation pipeline started."}


@router.get("/")
def list_videos():
    files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(".mp4")]
    return {
        "count": len(files),
        "videos": [
            {"filename": filename, "download_url": f"/api/videos/download/{filename}"}
            for filename in files
        ],
    }


@router.get("/videos/download/{filename}")
def download_video(filename: str):
    file_path = os.path.join(VIDEOS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")
