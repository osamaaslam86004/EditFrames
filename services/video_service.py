import os
import subprocess
from playwright.async_api import async_playwright
from core.config import get_settings
from services.tts_service import synthesize_voiceover
from services.subtitle_service import generate_subtitle_html
from core.websocket import manager

settings = get_settings()

VIDEOS_DIR = settings.videos_dir
BASE_DIR = settings.base_dir
TEMPLATE_PATH = settings.template_path

# Add aspect ratio dimension mapping inside services/video_service.py
ASPECT_RATIO_DIMENSIONS = {
    "9:16": {"width": 1080, "height": 1920},
    "1:1": {"width": 1080, "height": 1080},
    "16:9": {"width": 1920, "height": 1080},
}


def overlay_audio_to_video(video_path: str, audio_path: str, output_path: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        print(f"❌ FFmpeg Error: {result.stderr}")


def cleanup_old_videos():
    for filename in os.listdir(VIDEOS_DIR):
        file_path = os.path.join(VIDEOS_DIR, filename)
        if os.path.isfile(file_path) and filename.endswith(".mp4"):
            os.remove(file_path)


async def render_product_video(
    product: dict, browser, idx: int, total: int, aspect_ratio: str = "9:16"
):

    # 1. Resolve dimensions based on requested aspect ratio
    dims = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, ASPECT_RATIO_DIMENSIONS["9:16"])
    width, height = dims["width"], dims["height"]

    category = product.get("category", "general")

    await manager.broadcast(
        f"[{idx}/{total}] Generating LLM script & synthesizing voice ({category}) and & subtitle timings... for format {aspect_ratio}"
    )

    # 2. Synthesize voiceover and get script text & audio duration
    wav_path, voice_persona, audio_duration, script_text = synthesize_voiceover(product)
    record_duration_ms = int((audio_duration + 1.0) * 1000)

    # 3. Generate karaoke subtitle HTML spans
    subtitles_html = generate_subtitle_html(script_text, audio_duration)

    await manager.broadcast(
        f"[{idx}/{total}] Recording {aspect_ratio} video with voice persona '{voice_persona}' and animated subtitles ({audio_duration:.1f}s)..."
    )

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_template = f.read()

    # 4. Inject product details and subtitle spans into template
    rendered_html = (
        html_template.replace("{{PRODUCT_TITLE}}", product["title"])
        .replace("{{PRICE}}", str(product["price"]))
        .replace("{{IMAGE_URL}}", product["image"])
        .replace("{{SUBTITLES_HTML}}", subtitles_html)
        .replace("{{ASPECT_RATIO_CLASS}}", f"ratio-{aspect_ratio.replace(':', '-')}")
    )

    temp_html_path = os.path.join(BASE_DIR, f"temp_{product['id']}.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    # 5. Configure Playwright context with dynamic dimensions
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        record_video_dir=VIDEOS_DIR,
        record_video_size={"width": width, "height": height},
    )

    page = await context.new_page()
    await page.goto(f"file://{temp_html_path}", wait_until="networkidle")
    await page.wait_for_selector("img")

    # # Playwright records the canvas precisely while CSS animations play
    await page.wait_for_timeout(record_duration_ms)
    await context.close()

    raw_video_path = await page.video.path()
    final_mp4_path = os.path.join(VIDEOS_DIR, f"product_{product['id']}.mp4")

    overlay_audio_to_video(raw_video_path, wav_path, final_mp4_path)

    for pth in [raw_video_path, wav_path, temp_html_path]:
        if os.path.exists(pth):
            os.remove(pth)

    await manager.broadcast(
        f" Created {aspect_ratio} video with voiceover: product_{product['id']}.mp4"
    )
