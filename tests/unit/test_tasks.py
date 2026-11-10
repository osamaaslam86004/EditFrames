from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workers.tasks import run_pipeline


@pytest.mark.asyncio
async def test_run_pipeline_custom_payload():
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
    ):
        mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
        mock_create_job.return_value = "job-chair-123"

        await run_pipeline(payload)

        # 1. Job created with correct title
        mock_create_job.assert_called_once_with(
            mock_sessionmaker, "Ergonomic Office Chair"
        )

        # 2. Status updated to processing then completed
        assert mock_update_status.call_count == 2
        mock_update_status.assert_any_call(
            mock_sessionmaker, "job-chair-123", "processing"
        )

        # 3. render_product_video called with correct custom product and aspect ratio
        mock_render.assert_called_once()
        product_arg, browser_arg, idx, total = mock_render.call_args[0]
        aspect_ratio_kwarg = mock_render.call_args[1].get("aspect_ratio")

        assert product_arg["title"] == "Ergonomic Office Chair"
        assert product_arg["price"] == 249.50
        assert product_arg["image"] == "https://example.com/chair.png"
        assert product_arg["voice_persona"] == "af_nicole"
        assert aspect_ratio_kwarg == "1:1"

        # 4. Final status updated to completed with output_url
        completed_call = mock_update_status.call_args_list[1]
        assert completed_call[0][1] == "job-chair-123"
        assert completed_call[0][2] == "completed"
        assert "output_url" in completed_call[1]
        assert "product_custom_" in completed_call[1]["output_url"]

        # 5. Engine disposed
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_run_pipeline_fallback_batch():
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
    ):
        mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
        mock_httpx.return_value.__enter__.return_value.get.return_value = mock_response
        mock_create_job.side_effect = ["job-p1", "job-p2"]

        await run_pipeline(None)

        # Batch cleanup executed
        mock_cleanup.assert_called_once()
        # Render called for each product
        assert mock_render.call_count == 2
        # Engine disposed
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_run_pipeline_error_handling():
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
    ):
        mock_pw_ctx.return_value.__aenter__.return_value = mock_playwright
        mock_create_job.return_value = "job-fail-1"
        mock_render.side_effect = RuntimeError("Playwright render crashed")

        with pytest.raises(RuntimeError, match="Playwright render crashed"):
            await run_pipeline(payload)

        # Verify job marked as failed
        failed_call = mock_update_status.call_args_list[-1]
        assert failed_call[0][1] == "job-fail-1"
        assert failed_call[0][2] == "failed"
        assert "Playwright render crashed" in failed_call[1]["error_message"]

        # Ensure engine is still disposed
        mock_engine.dispose.assert_called_once()


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
