import asyncio
import httpx
import logging

from playwright.async_api import async_playwright
from sqlalchemy.future import select

from core.config import get_settings
from workers.celery_app import celery_app
from services.video_service import cleanup_old_videos, render_product_video
from db.session import AsyncSessionLocal
from db.models.videos_model import VideoJob

logger = logging.getLogger(__name__)
settings = get_settings()


async def create_job_record(product_title: str) -> str:
    """Create a new video job entry with 'pending' status."""
    async with AsyncSessionLocal() as session:
        job = VideoJob(product_title=product_title, status="pending")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job.id


async def update_job_status(
    job_id: str, status: str, output_url: str = None, error_message: str = None
):
    """Update an existing video job's status, output URL, or error details."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VideoJob).where(VideoJob.id == job_id))
        job = result.scalars().first()
        if job:
            job.status = status
            if output_url:
                job.output_url = output_url
            if error_message:
                job.error_message = error_message
            await session.commit()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_weekly_videos_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=settings.task_max_retries,
)
def generate_weekly_videos_task(self):
    try:
        print("🧹 Cleaning up old promo videos...")
        cleanup_old_videos()

        print("🌐 Fetching product payload from FakeStore API...")
        with httpx.Client() as client:
            response = client.get("https://fakestoreapi.com/products?limit=3")
            products = response.json()

        async def run_pipeline():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
                )

                for idx, product in enumerate(products, 1):
                    # 1. Create DB job entry
                    job_id = await create_job_record(product["title"])

                    try:
                        # 2. Update status to processing
                        await update_job_status(job_id, "processing")

                        # 3. Render video and audio voiceover
                        await render_product_video(product, browser, idx, len(products))

                        # 4. Mark job as completed with download URL
                        output_url = (
                            f"/api/v1/videos/download/product_{product['id']}.mp4"
                        )
                        await update_job_status(
                            job_id, "completed", output_url=output_url
                        )

                    except Exception as inner_exc:
                        # Mark job as failed with error message
                        await update_job_status(
                            job_id, "failed", error_message=str(inner_exc)
                        )
                        raise inner_exc

                await browser.close()

        # Run the async pipeline inside the sync Celery worker
        asyncio.run(run_pipeline())
        print("🎉 All AI Voiceover promo reels generated successfully via Celery!")
        return {"status": "success", "count": len(products)}

    except Exception as exc:
        print(f"❌ PIPELINE ERROR: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)
