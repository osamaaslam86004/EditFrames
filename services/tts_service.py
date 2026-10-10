import os
import subprocess
import torch
import soundfile as sf
from core.config import get_settings
from core.lifespan import models

settings = get_settings()
VIDEOS_DIR = settings.videos_dir


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


def generate_tts_script(product: dict) -> str:
    title = product.get("title", "")
    price = product.get("price", "")
    return f"Check out this deal! {title}. Now on sale for only {price} dollars. Grab yours today before it sells out!"


def synthesize_voiceover(product: dict) -> tuple[str, float]:
    script_text = generate_tts_script(product)
    wav_path = os.path.join(VIDEOS_DIR, f"voice_{product['id']}.wav")

    generator = models["tts"](script_text, voice="af_bella", speed=1.0)
    audio_chunks = [audio for _, _, audio in generator]

    combined_audio = (
        torch.cat(audio_chunks, dim=0).numpy()
        if len(audio_chunks) > 1
        else audio_chunks[0].numpy()
    )
    sf.write(wav_path, combined_audio, 24000)

    audio_duration = get_audio_duration(wav_path)
    return wav_path, audio_duration
