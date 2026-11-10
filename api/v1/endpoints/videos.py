import os
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse

from core.config import get_settings
from core.security import require_api_key
from schemas.app_schemas import VideoGenerateRequest
from services.tts_service import synthesize_voiceover_preview
from workers.tasks import generate_weekly_videos_task

router = APIRouter(
    prefix="/v1/videos",
    tags=["Videos"],
    dependencies=[Depends(require_api_key)],
)

legacy_router = APIRouter(
    tags=["Videos Legacy"],
    dependencies=[Depends(require_api_key)],
)

settings = get_settings()

VIDEOS_DIR = settings.videos_dir


@router.post("/generate")
async def trigger_generation(
    payload: VideoGenerateRequest | None = Body(default=None),
):
    """Triggers video generation with optional custom dashboard parameters.

    Accepts VideoGenerateRequest containing product_title, price, image_url,
    voice_persona, aspect_ratio, and use_llm_script.
    Passes custom payload dictionary to Celery worker task.
    If no payload is provided, Celery worker falls back to batch generation.
    """
    task_data = payload.model_dump() if payload else None
    task = generate_weekly_videos_task.delay(task_data)

    return {
        "status": "started",
        "task_id": task.id,
        "message": "Video generation pipeline dispatched to Celery worker.",
    }


@router.get("", include_in_schema=False)
@router.get("/")
def list_videos():
    files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(".mp4")]
    return {
        "count": len(files),
        "videos": [
            {
                "filename": filename,
                "download_url": f"/api/v1/videos/download/{filename}",
            }
            for filename in files
        ],
    }


@router.get("/download/{filename}")
@router.get("/videos/download/{filename}", include_in_schema=False)
def download_video(filename: str):
    file_path = os.path.join(VIDEOS_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found.")

    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")


# Legacy routes for dashboard UI compatibility
@legacy_router.get("/videos", include_in_schema=False)
def legacy_list_videos():
    return list_videos()


@legacy_router.get("/videos/download/{filename}", include_in_schema=False)
def legacy_download_video(filename: str):
    return download_video(filename)


@legacy_router.post("/generate-now", include_in_schema=False)
async def legacy_generate_now():
    return await trigger_generation(None)


@router.post("/preview-audio")
async def preview_audio(payload: VideoGenerateRequest):
    """Generates a temporary Kokoro voiceover file for instant audio preview."""
    try:
        product_dict = {
            "id": f"preview_{uuid.uuid4().hex[:8]}",
            "title": payload.product_title,
            "price": payload.price,
            "category": "electronics",  # Default fallback for preview mapping
        }

        # Synthesize preview audio using the selected voice persona
        wav_path, voice_persona = synthesize_voiceover_preview(
            product_dict, payload.voice_persona
        )
        filename = os.path.basename(wav_path)

        return {
            "status": "success",
            "voice_persona": voice_persona,
            "preview_url": f"/api/v1/videos/preview-audio/stream/{filename}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Audio preview generation failed: {e!s}"
        )


@router.get("/preview-audio/stream/{filename}")
def stream_preview_audio(filename: str):
    file_path = os.path.join(settings.videos_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Preview audio file not found.")

    return FileResponse(path=file_path, media_type="audio/wav")
