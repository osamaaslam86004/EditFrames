from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.config import get_settings
from core.lifespan import lifespan
from api.v1.router import api_router as api
from api.v1.router import ws_router as ws

settings = get_settings()
STATIC_DIR = settings.static_dir

app = FastAPI(
    title=settings.app.app_name,
    description=settings.app.description,
    version=settings.app.api_v1_prefix,
    lifespan=lifespan,
)

app.mount("/dashboard", StaticFiles(directory=STATIC_DIR, html=True), name="static")

app.include_router(api, prefix="/api")
app.include_router(ws, prefix="/ws")


@app.get("/")
def root():
    return {
        "message": "KittenTTS Video Studio running. Access dashboard at {settings.app.dashboard_url}"
    }
