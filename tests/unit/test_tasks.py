import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from celery.exceptions import SoftTimeLimitExceeded

from workers.celery_app import celery_app
from workers.tasks import generate_weekly_videos_task, run_pipeline


class TestTasks(unittest.IsolatedAsyncioTestCase):
    async def test_run_pipeline_custom_payload(self):
        payload = {
            "product_title": "Ergonomic Office Chair",
            "price": 249.50,
            "image_url": "https://example.com/chair.png",
            "voice_persona": "af_nicole",
            "aspect_ratio": "1:1",
            "use_llm_script": True,
        }
        mock_engine = AsyncMock()
        mock_sessionmaker = MagicMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        with (
            patch(
                "workers.tasks.get_task_sessionmaker",
                return_value=(mock_engine, mock_sessionmaker),
            ),
            patch("workers.tasks.async_playwright") as mock_pw_ctx,
            patch(
                "workers.tasks.create_job_record", new_callable=AsyncMock
            ) as mock_create_job,
            patch(
                "workers.tasks.update_job_status", new_callable=AsyncMock
            ) as mock_update_status,
            patch(
                "workers.tasks.render_product_video", new_callable=AsyncMock
            ) as mock_render,
            patch(
                "workers.tasks.upload_video_to_storage",
                return_value="https://example.com/videos/product_custom_chair.mp4",
            ) as mock_storage,
            patch("workers.tasks.cleanup_temporary_files") as mock_cleanup_files,
        ):
            mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
            mock_create_job.return_value = "job-chair-123"

            await run_pipeline(payload)

            # 1. Job created with correct title
            mock_create_job.assert_called_once_with(
                mock_sessionmaker, "Ergonomic Office Chair"
            )
            # 2. Status updated to processing then completed
            self.assertEqual(mock_update_status.call_count, 2)
            mock_update_status.assert_any_call(
                mock_sessionmaker, "job-chair-123", "processing"
            )
            # 3. render_product_video called with correct custom product and aspect ratio
            mock_render.assert_called_once()
            product_arg = mock_render.call_args[0][0]
            aspect_ratio_kwarg = mock_render.call_args[1].get("aspect_ratio")
            self.assertEqual(product_arg["title"], "Ergonomic Office Chair")
            self.assertEqual(product_arg["price"], 249.50)
            self.assertEqual(product_arg["image"], "https://example.com/chair.png")
            self.assertEqual(product_arg["voice_persona"], "af_nicole")
            self.assertEqual(aspect_ratio_kwarg, "1:1")
            # 4. Final status updated to completed with output_url
            completed_call = mock_update_status.call_args_list[1]
            self.assertEqual(completed_call[0][1], "job-chair-123")
            self.assertEqual(completed_call[0][2], "completed")
            self.assertIn("output_url", completed_call[1])
            # 5. Cleanup called & Engine disposed
            mock_cleanup_files.assert_called_once()
            mock_engine.dispose.assert_called_once()

    async def test_run_pipeline_fallback_batch(self):
        mock_engine = AsyncMock()
        mock_sessionmaker = MagicMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        fake_products = [
            {
                "id": "p1",
                "title": "Fake Product 1",
                "price": 19.99,
                "image": "http://img1.jpg",
                "category": "electronics",
            },
            {
                "id": "p2",
                "title": "Fake Product 2",
                "price": 29.99,
                "image": "http://img2.jpg",
                "category": "jewelery",
            },
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = fake_products

        with (
            patch(
                "workers.tasks.get_task_sessionmaker",
                return_value=(mock_engine, mock_sessionmaker),
            ),
            patch("workers.tasks.async_playwright") as mock_pw_ctx,
            patch("workers.tasks.cleanup_old_videos") as mock_cleanup,
            patch("httpx.Client") as mock_httpx,
            patch(
                "workers.tasks.create_job_record", new_callable=AsyncMock
            ) as mock_create_job,
            patch(
                "workers.tasks.update_job_status", new_callable=AsyncMock
            ) as mock_update_status,
            patch(
                "workers.tasks.render_product_video", new_callable=AsyncMock
            ) as mock_render,
            patch(
                "workers.tasks.upload_video_to_storage",
                return_value="https://example.com/videos/mock_batch.mp4",
            ) as mock_storage,
            patch("workers.tasks.cleanup_temporary_files") as mock_cleanup_files,
        ):
            mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
            mock_httpx.return_value.__enter__.return_value.get.return_value = (
                mock_response
            )
            mock_create_job.side_effect = ["job-p1", "job-p2"]

            await run_pipeline(None)

            # Batch cleanup executed
            mock_cleanup.assert_called_once()
            # Render called for each product
            self.assertEqual(mock_render.call_count, 2)
            self.assertEqual(mock_cleanup_files.call_count, 2)
            # Engine disposed
            mock_engine.dispose.assert_called_once()

    async def test_run_pipeline_error_handling(self):
        payload = {
            "product_title": "Faulty Product",
            "price": 9.99,
            "image_url": "https://example.com/faulty.jpg",
        }
        mock_engine = AsyncMock()
        mock_sessionmaker = MagicMock()
        mock_playwright = AsyncMock()

        with (
            patch(
                "workers.tasks.get_task_sessionmaker",
                return_value=(mock_engine, mock_sessionmaker),
            ),
            patch("workers.tasks.async_playwright") as mock_pw_ctx,
            patch(
                "workers.tasks.create_job_record", new_callable=AsyncMock
            ) as mock_create_job,
            patch(
                "workers.tasks.update_job_status", new_callable=AsyncMock
            ) as mock_update_status,
            patch(
                "workers.tasks.render_product_video", new_callable=AsyncMock
            ) as mock_render,
            patch("workers.tasks.cleanup_temporary_files") as mock_cleanup_files,
        ):
            mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
            mock_create_job.return_value = "job-fail-1"
            mock_render.side_effect = RuntimeError("Playwright render crashed")

            with self.assertRaises(RuntimeError):
                await run_pipeline(payload)

            # Verify job marked as failed with truncated error message
            failed_call = mock_update_status.call_args_list[-1]
            self.assertEqual(failed_call[0][1], "job-fail-1")
            self.assertEqual(failed_call[0][2], "failed")
            self.assertIn("Playwright render crashed", failed_call[1]["error_message"])
            # Temporary files cleaned up & Engine disposed
            mock_cleanup_files.assert_called_once()
            mock_engine.dispose.assert_called_once()

    async def test_run_pipeline_http_error_handling(self):
        mock_engine = AsyncMock()
        mock_sessionmaker = MagicMock()
        mock_playwright = AsyncMock()

        with (
            patch(
                "workers.tasks.get_task_sessionmaker",
                return_value=(mock_engine, mock_sessionmaker),
            ),
            patch("workers.tasks.async_playwright") as mock_pw_ctx,
            patch("workers.tasks.cleanup_old_videos"),
            patch("httpx.Client") as mock_httpx,
        ):
            mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
            mock_httpx.return_value.__enter__.return_value.get.side_effect = (
                httpx.ConnectTimeout("API connection timed out")
            )

            with self.assertRaises(RuntimeError):
                await run_pipeline(None)

            mock_engine.dispose.assert_called_once()

    async def test_run_pipeline_soft_time_limit_exceeded(self):
        payload = {
            "product_title": "Slow Product",
            "price": 49.99,
            "image_url": "https://example.com/slow.jpg",
        }
        mock_engine = AsyncMock()
        mock_sessionmaker = MagicMock()

        with (
            patch(
                "workers.tasks.get_task_sessionmaker",
                return_value=(mock_engine, mock_sessionmaker),
            ),
            patch("workers.tasks.async_playwright") as mock_pw_ctx,
            patch(
                "workers.tasks.create_job_record", new_callable=AsyncMock
            ) as mock_create_job,
            patch(
                "workers.tasks.update_job_status", new_callable=AsyncMock
            ) as mock_update_status,
            patch("workers.tasks.cleanup_temporary_files") as mock_cleanup_files,
        ):
            mock_pw_ctx.side_effect = SoftTimeLimitExceeded()
            mock_create_job.return_value = "job-slow-99"

            with self.assertRaises(RuntimeError):
                await run_pipeline(payload)

            mock_engine.dispose.assert_called_once()


class TestCeleryConfig(unittest.TestCase):
    def test_celery_configuration_and_task_retries(self):
        conf = celery_app.conf
        self.assertEqual(conf.task_time_limit, 180)
        self.assertEqual(conf.task_soft_time_limit, 150)
        self.assertTrue(conf.task_acks_late)
        self.assertEqual(conf.worker_prefetch_multiplier, 1)

        task = generate_weekly_videos_task
        self.assertEqual(task.autoretry_for, (Exception,))
        self.assertTrue(task.retry_backoff)
        self.assertTrue(task.retry_jitter)


@pytest.mark.asyncio
async def test_run_pipeline_with_s3_storage_url():
    payload = {
        "product_title": "Smart Ring",
        "price": 199.00,
        "image_url": "https://example.com/ring.jpg",
    }

    mock_engine = AsyncMock()
    mock_sessionmaker = MagicMock()
    mock_playwright = AsyncMock()

    s3_cloud_url = (
        "https://editframes-bucket.s3.amazonaws.com/videos/product_custom_ring.mp4"
    )

    with (
        patch(
            "workers.tasks.get_task_sessionmaker",
            return_value=(mock_engine, mock_sessionmaker),
        ),
        patch("workers.tasks.async_playwright") as mock_pw_ctx,
        patch(
            "workers.tasks.create_job_record", new_callable=AsyncMock
        ) as mock_create_job,
        patch(
            "workers.tasks.update_job_status", new_callable=AsyncMock
        ) as mock_update_status,
        patch(
            "workers.tasks.render_product_video", new_callable=AsyncMock
        ) as mock_render,
        patch(
            "workers.tasks.upload_video_to_storage", return_value=s3_cloud_url
        ) as mock_storage,
    ):
        mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
        mock_create_job.return_value = "job-ring-99"

        await run_pipeline(payload)

        mock_storage.assert_called_once()
        completed_call = mock_update_status.call_args_list[1]
        assert completed_call[1]["output_url"] == s3_cloud_url
