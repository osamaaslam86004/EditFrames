import uuid
import asyncio
import httpx
import logging

from playwright.async_api import async_playwright

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import get_settings
from workers.celery_app import celery_app
from services.video_service import cleanup_old_videos, render_product_video
from db.models.videos_model import VideoJob

logger = logging.getLogger(__name__)
settings = get_settings()


# 1. Reuse central settings to resolve database URL and async driver
ASYNC_DB_URL = str(settings.db.async_url)


def get_task_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Creates an async engine and sessionmaker per task execution using NullPool.
    Prevents cross-event-loop connection contamination when using asyncio.run().
    """

    _worker_engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    _worker_sessionmaker = async_sessionmaker(
        _worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _worker_engine, _worker_sessionmaker


async def create_job_record(
    sessionmaker: async_sessionmaker[AsyncSession], product_title: str
) -> str:
    """Create a new video job entry with 'pending' status using the task-local sessionmaker."""

    async with sessionmaker() as session:
        job = VideoJob(product_title=product_title, status="pending")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def update_job_status(
    sessionmaker: async_sessionmaker[AsyncSession],
    job_id: str,
    status: str,
    output_url: str = None,
    error_message: str = None,
):
    """Update an existing video job's status, output URL, or error details
    using the task-local sessionmaker."""

    async with sessionmaker() as session:
        result = await session.execute(select(VideoJob).where(VideoJob.id == job_id))
        job = result.scalars().first()

        if job:
            job.status = status
            if output_url:
                job.output_url = output_url
            if error_message:
                job.error_message = error_message
            await session.commit()


async def run_pipeline(payload: dict | None = None):

    # Initialize a fresh engine and sessionmaker for this specific event loop / task run
    engine, sessionmaker = get_task_sessionmaker()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )

            if payload:
                # Render custom single video from dashboard payload
                print("Processing custom generation request from dashboard...")
                product = {
                    "id": f"custom_{uuid.uuid4().hex[:8]}",
                    "title": payload.get("product_title"),
                    "price": payload.get("price"),
                    "image": payload.get("image_url"),
                    "category": "electronics",
                    "voice_persona": payload.get("voice_persona", "af_bella"),
                }

                aspect_ratio = payload.get("aspect_ratio", "9:16")

                # 1. Create DB job entry
                job_id = await create_job_record(sessionmaker, product["title"])

                # 2. Update status to processing
                await update_job_status(sessionmaker, job_id, "processing")

                try:
                    # 3. Render video and audio voiceover
                    await render_product_video(
                        product, browser, 1, 1, aspect_ratio=aspect_ratio
                    )

                    # 4. Mark job as completed with download URL
                    output_url = f"/api/v1/videos/download/product_{product['id']}.mp4"
                    await update_job_status(
                        sessionmaker, job_id, "completed", output_url=output_url
                    )

                except Exception as inner_exc:
                    # Mark job as failed with error message
                    await update_job_status(
                        sessionmaker, job_id, "failed", error_message=str(inner_exc)
                    )
                    raise inner_exc

            else:

                # Fallback batch cron job behavior
                print("Cleaning up old promo videos...")
                cleanup_old_videos()

                print("Fetching product payload from FakeStore API...")
                with httpx.Client() as client:
                    response = client.get("https://fakestoreapi.com/products?limit=3")
                    products = response.json()

                for idx, product in enumerate(products, 1):

                    job_id = await create_job_record(sessionmaker, product["title"])

                    await update_job_status(sessionmaker, job_id, "processing")

                    try:
                        await render_product_video(
                            product,
                            browser,
                            idx,
                            len(products),
                            aspect_ratio="9:16",
                        )
                        output_url = (
                            f"/api/v1/videos/download/product_{product['id']}.mp4"
                        )
                        await update_job_status(
                            sessionmaker, job_id, "completed", output_url=output_url
                        )

                    except Exception as inner_exc:
                        await update_job_status(
                            sessionmaker, job_id, "failed", error_message=str(inner_exc)
                        )
                        raise inner_exc

            await browser.close()

    finally:
        # Ensure database connections are cleaned up and engine is disposed of when the task finishes
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_weekly_videos_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=settings.celery.task_max_retries,
)
def generate_weekly_videos_task(self, payload: dict | None = None):
    try:
        # Run the async pipeline inside the sync Celery worker
        asyncio.run(run_pipeline(payload))
        print("Video generation completed successfully via Celery!")
        return {"status": "success"}

    except Exception as exc:
        print(f"PIPELINE ERROR: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)
