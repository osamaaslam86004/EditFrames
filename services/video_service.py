import os
import subprocess
from playwright.async_api import async_playwright
from core.config import get_settings
from services.tts_service import synthesize_voiceover, get_audio_duration
from core.websocket import manager

settings = get_settings()

VIDEOS_DIR = settings.videos_dir
BASE_DIR = settings.base_dir
TEMPLATE_PATH = settings.template_path


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


async def render_product_video(product: dict, browser, idx: int, total: int):
    category = product.get("category", "general")
    await manager.broadcast(
        f"[{idx}/{total}] Generating LLM script & synthesizing voice ({category})..."
    )
    wav_path, voice_persona, audio_duration = synthesize_voiceover(product)
    record_duration_ms = int((audio_duration + 1.0) * 1000)

    await manager.broadcast(
        f"[{idx}/{total}] Recording video with voice persona '{voice_persona}' ({audio_duration:.1f}s)..."
    )

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_template = f.read()

    rendered_html = (
        html_template.replace("{{PRODUCT_TITLE}}", product["title"])
        .replace("{{PRICE}}", str(product["price"]))
        .replace("{{IMAGE_URL}}", product["image"])
    )

    temp_html_path = os.path.join(BASE_DIR, f"temp_{product['id']}.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    context = await browser.new_context(
        viewport={"width": 1080, "height": 1920},
        record_video_dir=VIDEOS_DIR,
        record_video_size={"width": 1080, "height": 1920},
    )

    page = await context.new_page()
    await page.goto(f"file://{temp_html_path}", wait_until="networkidle")
    await page.wait_for_selector("img")
    await page.wait_for_timeout(record_duration_ms)
    await context.close()

    raw_video_path = await page.video.path()
    final_mp4_path = os.path.join(VIDEOS_DIR, f"product_{product['id']}.mp4")

    overlay_audio_to_video(raw_video_path, wav_path, final_mp4_path)

    for pth in [raw_video_path, wav_path, temp_html_path]:
        if os.path.exists(pth):
            os.remove(pth)

    await manager.broadcast(
        f"✅ Created video with voiceover: product_{product['id']}.mp4"
    )
