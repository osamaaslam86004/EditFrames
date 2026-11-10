import asyncio
import logging
import os
import traceback
import uuid

import httpx
from celery.exceptions import SoftTimeLimitExceeded
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
from db.models.videos_model import VideoJob
from services.storage_service import upload_video_to_storage
from services.video_service import cleanup_old_videos, render_product_video
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()
VIDEOS_DIR = settings.videos_dir

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
    output_url: str | None = None,
    error_message: str | None = None,
):
    """Update an existing video job's status, output URL, or error details
    using the task-local sessionmaker."""
    async with sessionmaker() as session:
        result = await session.execute(select(VideoJob).where(VideoJob.id == job_id))
        job = result.scalars().first()
        if job:
            job.status = status
            if output_url is not None:
                job.output_url = output_url
            if error_message is not None:
                job.error_message = error_message
            await session.commit()


def cleanup_temporary_files(product_id: str):
    """Safely removes temporary files (.html, .wav, raw mp4) associated with a product rendering."""
    base_dir = settings.base_dir
    temp_files = [
        os.path.join(base_dir, f"temp_{product_id}.html"),
        os.path.join(VIDEOS_DIR, f"voice_{product_id}.wav"),
        os.path.join(VIDEOS_DIR, f"raw_{product_id}.webm"),
    ]
    for file_path in temp_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("Cleaned up temporary file: %s", file_path)
            except Exception as e:
                logger.warning("Could not clean up temporary file %s: %s", file_path, e)


async def run_pipeline(payload: dict | None = None):
    engine, sessionmaker = get_task_sessionmaker()
    current_job_id = None
    product_id = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            try:
                if payload:
                    # Render custom single video from dashboard payload
                    product_title = payload.get("product_title", "Untitled Product")
                    price = payload.get("price", 0.0)
                    image_url = payload.get("image_url", "")
                    voice_persona = payload.get("voice_persona", "af_bella")
                    aspect_ratio = payload.get("aspect_ratio", "9:16")
                    use_llm_script = payload.get("use_llm_script", True)
                    category = payload.get("category", "electronics")

                    product_id = f"custom_{uuid.uuid4().hex[:8]}"
                    logger.info(
                        "Processing custom generation request from dashboard: title='%s', price=%s, aspect_ratio=%s, voice_persona=%s",
                        product_title,
                        price,
                        aspect_ratio,
                        voice_persona,
                    )
                    product = {
                        "id": product_id,
                        "title": product_title,
                        "price": price,
                        "image": image_url,
                        "category": category,
                        "voice_persona": voice_persona,
                        "use_llm_script": use_llm_script,
                    }
                    current_job_id = await create_job_record(
                        sessionmaker, product["title"]
                    )
                    await update_job_status(sessionmaker, current_job_id, "processing")
                    try:
                        await render_product_video(
                            product, browser, 1, 1, aspect_ratio=aspect_ratio
                        )
                        video_filename = f"product_{product['id']}.mp4"
                        local_mp4_path = os.path.join(VIDEOS_DIR, video_filename)
                        output_url = upload_video_to_storage(
                            local_mp4_path, destination_key=f"videos/{video_filename}"
                        )
                        await update_job_status(
                            sessionmaker,
                            current_job_id,
                            "completed",
                            output_url=output_url,
                        )
                        logger.info(
                            "Custom video generation job %s completed successfully: %s",
                            current_job_id,
                            output_url,
                        )
                    except Exception as inner_exc:
                        formatted_err = f"{inner_exc!s}\n{traceback.format_exc()}"[
                            -1000:
                        ]
                        logger.error(
                            "Custom video generation job %s failed: %s",
                            current_job_id,
                            formatted_err,
                        )
                        await update_job_status(
                            sessionmaker,
                            current_job_id,
                            "failed",
                            error_message=formatted_err,
                        )
                        raise inner_exc
                    finally:
                        cleanup_temporary_files(product_id)
                else:
                    # Fallback batch cron job behavior
                    logger.info(
                        "No custom payload provided. Executing batch FakeStore run..."
                    )
                    cleanup_old_videos()
                    logger.info("Fetching product payload from FakeStore API...")
                    try:
                        with httpx.Client(timeout=30.0) as client:
                            response = client.get(
                                "https://fakestoreapi.com/products?limit=3"
                            )
                            response.raise_for_status()
                            products = response.json()
                    except (httpx.HTTPError, httpx.RequestError) as http_err:
                        err_msg = f"External API request failed: {http_err!s}"
                        logger.error("FakeStore API error: %s", err_msg)
                        raise RuntimeError(err_msg) from http_err

                    for idx, product in enumerate(products, 1):
                        p_id = product.get("id", f"batch_{idx}")
                        current_job_id = await create_job_record(
                            sessionmaker, product["title"]
                        )
                        await update_job_status(
                            sessionmaker, current_job_id, "processing"
                        )
                        try:
                            await render_product_video(
                                product,
                                browser,
                                idx,
                                len(products),
                                aspect_ratio="9:16",
                            )
                            video_filename = f"product_{product['id']}.mp4"
                            local_mp4_path = os.path.join(VIDEOS_DIR, video_filename)
                            output_url = upload_video_to_storage(
                                local_mp4_path,
                                destination_key=f"videos/{video_filename}",
                            )
                            await update_job_status(
                                sessionmaker,
                                current_job_id,
                                "completed",
                                output_url=output_url,
                            )
                            logger.info(
                                "Batch video %s/%s completed: %s",
                                idx,
                                len(products),
                                output_url,
                            )
                        except Exception as inner_exc:
                            formatted_err = f"{inner_exc!s}\n{traceback.format_exc()}"[
                                -1000:
                            ]
                            logger.error(
                                "Batch video job %s failed: %s",
                                current_job_id,
                                formatted_err,
                            )
                            await update_job_status(
                                sessionmaker,
                                current_job_id,
                                "failed",
                                error_message=formatted_err,
                            )
                            raise inner_exc
                        finally:
                            cleanup_temporary_files(str(p_id))
            finally:
                await browser.close()
    except SoftTimeLimitExceeded as stl_exc:
        err_msg = "Job execution exceeded soft time limit (150s)"
        logger.warning("SoftTimeLimitExceeded caught in run_pipeline: %s", err_msg)
        if current_job_id:
            await update_job_status(
                sessionmaker, current_job_id, "failed", error_message=err_msg
            )
        if product_id:
            cleanup_temporary_files(product_id)
        raise RuntimeError(err_msg) from stl_exc
    finally:
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
        logger.info(
            "Executing generate_weekly_videos_task with payload: %s",
            "custom" if payload else "batch",
        )
        asyncio.run(run_pipeline(payload))
        logger.info("Video generation completed successfully via Celery!")
        return {"status": "success"}
    except Exception as exc:
        logger.error("PIPELINE TASK ERROR: %s", str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=60)
