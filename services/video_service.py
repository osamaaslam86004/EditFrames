import os
import subprocess

from core.config import get_settings
from core.websocket import manager
from services.subtitle_service import generate_subtitle_html
from services.tts_service import synthesize_voiceover

settings = get_settings()
VIDEOS_DIR = settings.videos_dir
BASE_DIR = settings.base_dir
TEMPLATE_PATH = settings.template_path

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BGM_PATH = os.path.join(ASSETS_DIR, "bgm.mp3")

# Aspect ratio dimension mapping (9:16 vertical, 1:1 square, 16:9 landscape)
ASPECT_RATIO_DIMENSIONS = {
    "9:16": {"width": 1080, "height": 1920},
    "1:1": {"width": 1080, "height": 1080},
    "16:9": {"width": 1920, "height": 1080},
}


def overlay_audio_to_video(video_path: str, audio_path: str, output_path: str):
    """
    Mixes Playwright silent video, Kokoro voiceover, and BGM with automatic
    sidechain compression (ducking).
    """
    if not os.path.exists(BGM_PATH):
        print(
            "bgm.mp3 not found in assets/. Falling back to standard voiceover overlay."
        )
        cmd_fallback = [
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
        subprocess.run(
            cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-i",
        audio_path,
        "-i",
        BGM_PATH,
        "-filter_complex",
        (
            "[2:a]volume=0.2[bgm_base];"
            "[bgm_base][1:a]sidechaincompress=threshold=0.02:ratio=6:attack=10:release=250[bgm_ducked];"
            "[1:a][bgm_ducked]amix=inputs=2:duration=first[final_audio]"
        ),
        "-map",
        "0:v",
        "-map",
        "[final_audio]",
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
        print(f"❌ FFmpeg Ducking Error: {result.stderr}")


def cleanup_old_videos():
    if os.path.exists(VIDEOS_DIR):
        for filename in os.listdir(VIDEOS_DIR):
            file_path = os.path.join(VIDEOS_DIR, filename)
            if os.path.isfile(file_path) and filename.endswith(".mp4"):
                try:
                    os.remove(file_path)
                except Exception:
                    pass


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

    # Resolve template path dynamically
    template_file = TEMPLATE_PATH
    if not template_file or not os.path.exists(template_file):
        template_file = os.path.join(BASE_DIR, "frontend", "templates", "template.html")
    if not os.path.exists(template_file):
        template_file = os.path.join(BASE_DIR, "template.html")

    with open(template_file, "r", encoding="utf-8") as f:
        html_template = f.read()

    # 4. Inject product details, subtitles, and aspect ratio class into template
    product_title = product.get("title", "Product")
    price = str(product.get("price", "0.00"))
    image_url = product.get("image") or product.get("image_url", "")

    rendered_html = (
        html_template.replace("{{PRODUCT_TITLE}}", product_title)
        .replace("{{PRICE}}", price)
        .replace("{{IMAGE_URL}}", image_url)
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

    # Playwright records canvas while CSS keyframe animations play
    await page.wait_for_timeout(record_duration_ms)
    await context.close()

    raw_video_path = await page.video.path()
    final_mp4_path = os.path.join(VIDEOS_DIR, f"product_{product['id']}.mp4")

    # Mix audio with BGM ducking and video
    overlay_audio_to_video(raw_video_path, wav_path, final_mp4_path)

    for pth in [raw_video_path, wav_path, temp_html_path]:
        if pth and os.path.exists(pth):
            try:
                os.remove(pth)
            except Exception:
                pass

    await manager.broadcast(
        f" Created BGM ducked promo reel {aspect_ratio} video with voiceover: product_{product['id']}.mp4"
    )
