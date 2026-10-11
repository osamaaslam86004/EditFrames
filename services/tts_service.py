import os
import subprocess
import torch
import soundfile as sf
from google import genai
from google.genai import types
from core.config import get_settings
from core.lifespan import models

settings = get_settings()
VIDEOS_DIR = settings.videos_dir

# Map FakeStore / product categories to Kokoro voice personas
CATEGORY_VOICE_MAP = {
    "electronics": "am_adam",  # Deep, authoritative tech voice
    "jewelery": "af_bella",  # Elegant, clear retail voice
    "men's clothing": "am_michael",  # Crisp, energetic male voice
    "women's clothing": "af_nicole",  # Smooth, engaging female voice
}
DEFAULT_VOICE = "af_bella"


def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)


def generate_dynamic_tts_script(product: dict) -> str:
    """Generate punchy, category-tailored sales copy via Gemini LLM with a fallback."""
    title = product.get("title", "")
    price = product.get("price", "")
    category = product.get("category", "general")

    # Retrieve Gemini API key from settings (ensure your config exposes gemini_api_key)
    api_key = settings.llm.gemini_api_key.get_secret_value()

    if not api_key:
        # Fallback if Gemini key is not configured
        return f"Check out this deal! {title}. Now on sale for only {price} dollars. Grab yours today before it sells out!"

    try:
        # Initialize the Google GenAI client
        client = genai.Client(api_key=api_key)

        prompt = (
            f"You are an expert e-commerce copywriter. Write a short, punchy, high-conversion "
            f"promotional voiceover script (under 25 words) for a social media short (TikTok/Reels).\n"
            f"Product Title: {title}\n"
            f"Category: {category}\n"
            f"Price: ${price}\n"
            f"Tone: Tailor tone to category (e.g., hype and urgent for electronics, luxury and elegant for jewelry). "
            f"Return *only* the script text with no extra commentary or quotation marks."
        )

        # Call Gemini model using generate_content
        model_name = getattr(settings.llm, "gemini_model", "gemini-2.5-flash")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=60,
            ),
        )

        script = response.text.strip() if response.text else ""
        return script if script else f"Don't miss out on {title} for just ${price}!"

    except Exception as e:
        print(
            f" Gemini Script generation failed ({str(e)}). Falling back to default template."
        )
        return f"Check out this deal! {title}. Now on sale for only {price} dollars. Grab yours today!"


def synthesize_voiceover(product: dict) -> tuple[str, str, float, str]:
    """Synthesize voiceover using category-mapped Kokoro voice personas."""
    script_text = generate_dynamic_tts_script(product)

    # Map category to voice persona
    category = product.get("category", "").lower()
    voice_persona = CATEGORY_VOICE_MAP.get(category, DEFAULT_VOICE)

    wav_path = os.path.join(VIDEOS_DIR, f"voice_{product['id']}.wav")

    generator = models["tts"](script_text, voice=voice_persona, speed=1.0)
    audio_chunks = [audio for _, _, audio in generator]

    combined_audio = (
        torch.cat(audio_chunks, dim=0).numpy()
        if len(audio_chunks) > 1
        else audio_chunks[0].numpy()
    )
    sf.write(wav_path, combined_audio, 24000)

    audio_duration = get_audio_duration(wav_path)
    return wav_path, voice_persona, audio_duration, script_text


def synthesize_voiceover_preview(
    product: dict, voice_persona: str | None = None
) -> tuple[str, str]:
    """
    Synthesize preview voiceover allowing an explicit voice persona override.
    """
    script_text = generate_dynamic_tts_script(product)

    # Fallback to category mapping if no explicit voice persona override is provided
    if not voice_persona:
        category = product.get("category", "").lower()
        voice_persona = CATEGORY_VOICE_MAP.get(category, DEFAULT_VOICE)

    wav_path = os.path.join(VIDEOS_DIR, f"voice_{product['id']}.wav")

    generator = models["tts"](script_text, voice=voice_persona, speed=1.0)
    audio_chunks = [audio for _, _, audio in generator]

    combined_audio = (
        torch.cat(audio_chunks, dim=0).numpy()
        if len(audio_chunks) > 1
        else audio_chunks[0].numpy()
    )
    sf.write(wav_path, combined_audio, 24000)

    return wav_path, voice_persona
