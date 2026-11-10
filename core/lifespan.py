import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from huggingface_hub import login, snapshot_download

from core.config import get_settings
from core.websocket import manager

try:
    from kokoro import KPipeline
except ImportError:
    KPipeline = None

logger = logging.getLogger(__name__)
settings = get_settings()
HF_TOKEN = settings.llm.hf_token

models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if HF_TOKEN:
        try:
            raw_token = (
                HF_TOKEN.get_secret_value()
                if hasattr(HF_TOKEN, "get_secret_value")
                else str(HF_TOKEN)
            )
            login(token=raw_token)
            logger.info("Successfully authenticated with Hugging Face Hub.")
        except Exception as e:
            logger.warning("Failed Hugging Face login: %s", str(e))

    if KPipeline is not None:
        try:
            logger.info("Downloading/Checking Kokoro-82M Model (~330 MB)...")
            snapshot_download(repo_id="hexgrad/Kokoro-82M")
            models["tts"] = KPipeline(lang_code="a")
            logger.info("Kokoro-82M Model Loaded Successfully...")
        except Exception as e:
            logger.error("Failed to load Kokoro-82M pipeline: %s", str(e))
    else:
        logger.warning("Kokoro package not installed. Skipping model pre-loading.")

    # Start Redis Pub/Sub backplane telemetry listener
    try:
        await manager.start()
    except Exception as exc:
        logger.warning("Could not start telemetry backplane: %s", exc)

    yield

    # Clean up backplane listener and models
    try:
        await manager.stop()
    except Exception as exc:
        logger.warning("Error stopping telemetry backplane: %s", exc)
    models.clear()
