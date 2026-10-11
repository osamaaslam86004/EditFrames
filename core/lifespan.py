import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from huggingface_hub import login, snapshot_download
from kokoro import KPipeline
from core.config import get_settings

settings = get_settings()
HF_TOKEN = settings.llm.hf_token

models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if HF_TOKEN:

        try:
            login(token=HF_TOKEN)
            print("Successfully authenticated with Hugging Face Hub.")
        except Exception as e:
            print(f"Failed Hugging Face login: {str(e)}")

    print("Downloading/Checking Kokoro-82M Model (~330 MB)...")

    snapshot_download(repo_id="hexgrad/Kokoro-82M")

    models["tts"] = KPipeline(lang_code="a")

    print("Kokoro-82M Model Loaded Successfully...")

    yield
    models.clear()
