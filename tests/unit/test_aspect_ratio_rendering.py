import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Provide lightweight import mocks if dependencies are absent in current test runtime
for mod in [
    "pydantic_settings",
    "redis",
    "redis.asyncio",
    "sqlalchemy",
    "sqlalchemy.ext.asyncio",
    "sqlalchemy.pool",
    "sqlalchemy.orm",
]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

if "google.genai" not in sys.modules:
    try:
        import google.genai
    except ImportError:
        mock_genai = MagicMock()
        sys.modules["google"] = MagicMock()
        sys.modules["google.genai"] = mock_genai
        sys.modules["google.genai.types"] = MagicMock()

from services.video_service import ASPECT_RATIO_DIMENSIONS, render_product_video


class TestAspectRatioRendering(unittest.TestCase):
    def test_aspect_ratio_dimensions_mapping(self):
        self.assertIn("9:16", ASPECT_RATIO_DIMENSIONS)
        self.assertIn("1:1", ASPECT_RATIO_DIMENSIONS)
        self.assertIn("16:9", ASPECT_RATIO_DIMENSIONS)

        self.assertEqual(
            ASPECT_RATIO_DIMENSIONS["9:16"], {"width": 1080, "height": 1920}
        )
        self.assertEqual(
            ASPECT_RATIO_DIMENSIONS["1:1"], {"width": 1080, "height": 1080}
        )
        self.assertEqual(
            ASPECT_RATIO_DIMENSIONS["16:9"], {"width": 1920, "height": 1080}
        )

    def test_flash_sale_reel_css_keyframes_and_overrides(self):
        css_paths = [
            "/workspace/scratch/repo_base/frontend/static/css/flash_sale_reel.css",
            "/workspace/scratch/repo_base/static/css/flash_sale_reel.css",
        ]
        found = False
        for pth in css_paths:
            if os.path.exists(pth):
                found = True
                with open(pth, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("@keyframes zoomIn", content)
                self.assertIn("@keyframes pulseGlow", content)
                self.assertIn("body.ratio-9-16", content)
                self.assertIn("body.ratio-1-1", content)
                self.assertIn("body.ratio-16-9", content)

        self.assertTrue(
            found, "flash_sale_reel.css was not found in static directories"
        )

    def test_render_product_video_aspect_ratios_all(self):
        async def run_all_ratios():
            repo_base = "/workspace/scratch/repo_base"
            mock_settings = MagicMock()
            mock_settings.videos_dir = "/tmp/test_videos"
            mock_settings.base_dir = repo_base
            mock_settings.template_path = os.path.join(
                repo_base, "frontend", "templates", "template.html"
            )

            for ratio, expected_class, expected_dims in [
                ("9:16", "ratio-9-16", {"width": 1080, "height": 1920}),
                ("1:1", "ratio-1-1", {"width": 1080, "height": 1080}),
                ("16:9", "ratio-16-9", {"width": 1920, "height": 1080}),
            ]:
                product = {
                    "id": f"test_aspect_{ratio.replace(':', '_')}",
                    "title": "Aspect Ratio Test Product",
                    "price": 99.99,
                    "image": "https://example.com/test.jpg",
                    "category": "electronics",
                }

                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                mock_video = MagicMock()

                mock_browser.new_context.return_value = mock_context
                mock_context.new_page.return_value = mock_page
                mock_page.video = mock_video
                mock_video.path = AsyncMock(return_value="/tmp/mock_raw_video.webm")

                with (
                    patch("services.video_service.settings", mock_settings),
                    patch("services.video_service.BASE_DIR", repo_base),
                    patch(
                        "services.video_service.TEMPLATE_PATH",
                        os.path.join(
                            repo_base, "frontend", "templates", "template.html"
                        ),
                    ),
                    patch("services.video_service.synthesize_voiceover") as mock_tts,
                    patch(
                        "services.video_service.generate_subtitle_html"
                    ) as mock_subtitles,
                    patch(
                        "services.video_service.overlay_audio_to_video"
                    ) as mock_overlay,
                    patch("services.video_service.manager.broadcast") as mock_ws,
                ):
                    mock_tts.return_value = (
                        "/tmp/mock_voice.wav",
                        "am_adam",
                        3.5,
                        "Check out this aspect ratio test!",
                    )
                    mock_subtitles.return_value = (
                        "<span class='highlight'>Check out</span>"
                    )

                    await render_product_video(
                        product, mock_browser, 1, 1, aspect_ratio=ratio
                    )

                    # Verify Playwright context created with correct viewport & record_video_size
                    mock_browser.new_context.assert_called_once()
                    kwargs = mock_browser.new_context.call_args[1]
                    self.assertEqual(kwargs["viewport"], expected_dims)
                    self.assertEqual(kwargs["record_video_size"], expected_dims)

                    # Verify page navigation
                    mock_page.goto.assert_called_once()
                    nav_url = mock_page.goto.call_args[0][0]
                    self.assertTrue(nav_url.startswith("file://"))

                    # Verify generated HTML file content has correct ratio class
                    temp_html_path = nav_url.replace("file://", "")
                    if os.path.exists(temp_html_path):
                        with open(temp_html_path, "r", encoding="utf-8") as f:
                            html_text = f.read()
                        self.assertIn(expected_class, html_text)
                        os.remove(temp_html_path)

        asyncio.run(run_all_ratios())


if __name__ == "__main__":
    unittest.main()
