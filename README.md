# 🎬 Automated Promo Video Generation Pipeline

An enterprise-grade, microservice-based automated video rendering engine and Web Studio that converts dynamic product data, HTML/CSS templates, and AI models into publication-ready promotional videos, TikToks, Instagram Reels, and YouTube Shorts.

---

## ✨ Key Features

- **⚡ FastAPI Asynchronous Architecture**: Production-grade async routing with Pydantic BaseSettings (`AppConfig`, `DBConfig`, `RedisConfig`, `LLMConfig`, `CeleryConfig`), dependency injection, multi-tenant API key authentication, and modular endpoints.
- **🌐 Web Studio Dashboard**: Interactive web GUI (hosted at `/dashboard`) built with Tailwind CSS and FontAwesome, featuring dynamic preview inputs, instant audio voiceover previews, aspect ratio selection, and live status updates.
- **🎬 Playwright Headless Recording**: Programmatic video generation using headless Chromium to capture HTML5 slide templates with smooth CSS keyframe animations.
- **🤖 Gemini 2.5 LLM Copywriting**: Dynamic, high-conversion sales copy generation (<25 words) tailored specifically to product categories using Google GenAI SDK.
- **🎙️ Kokoro-82M AI Voice Synthesis**: Integrated Hugging Face TTS pipeline (`KPipeline`) featuring category-mapped voice personas (`af_bella`, `am_adam`, `am_michael`, `af_nicole`) with instant preview audio streaming.
- **🎤 Dynamic Animated Karaoke Subtitles**: Automated staggered HTML span generation with word-by-word CSS animation delay alignment calculated from audio duration.
- **🎛️ Sidechain Audio Ducking**: Professional audio mixing using FFmpeg complex filtergraphs to automatically duck background music by 20% when voiceover speech is detected.
- **📐 Multi-Format Aspect Ratio Support**:
  - `9:16` (1080x1920) Vertical Reels, TikToks, and Shorts.
  - `1:1` (1080x1080) Square Social Feeds.
  - `16:9` (1920x1080) Landscape Ads and Web Banners.
- **🗄️ PostgreSQL & Celery Background Queue**: Persistence layer using SQLAlchemy 2.0 async ORM with `NullPool` isolation for Celery worker tasks backed by Redis.
- **📡 Real-Time WebSockets**: Live progress broadcasting via `/ws/progress` streaming step-by-step pipeline status updates directly to connected dashboard clients.
- **🐳 Production Containerization**: Multi-container Docker deployment managing web backend, Celery background worker, and Redis message broker.

## 🏗️ Architecture & System Overview

```
                               ┌────────────────────────────────────────┐
                               │       Tailwind CSS Web Studio          │
                               │   (Dashboard UI & WebSockets)          │
                               └───────────────────┬────────────────────┘
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FastAPI Backend                                          │
│                                                                                                │
│  ┌─────────────────────────┐   ┌──────────────────────────┐   ┌─────────────────────────────┐  │
│  │   Video Router          │   │  Voice Preview Stream    │   │   WebSocket Progress        │  │
│  │   /api/v1/videos        │   │  /api/v1/videos/preview  │   │   /ws/progress              │  │
│  └───────────┬─────────────┘   └─────────────┬────────────┘   └──────────────┬──────────────┘  │
└──────────────┼───────────────────────────────┼───────────────────────────────┼─────────────────┘
               │                               │                               │
               ▼                               ▼                               │
┌──────────────────────────────┐ ┌──────────────────────────┐                  │
│       Celery Worker          │ │   Kokoro-82M TTS Model   │                  │
│   (Redis Broker & Backend)   │ │  (Hugging Face Pipeline) │                  │
└──────────────┬───────────────┘ └─────────────┬────────────┘                  │
               │                               │                               │
               ▼                               ▼                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Video Processing Engine                                      │
│                                                                                                │
│  1. Script Gen: Google Gemini 2.5 Flash API                                                    │
│  2. DOM Render: Playwright Headless Chromium (HTML + Dynamic Subtitles)                         │
│  3. Audio Mix:  FFmpeg Filtergraph with Sidechain Music Ducking                                 │
└──────────────────────────────┬─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 PostgreSQL Database & Storage                                  │
│  - VideoJob State Records (Pending, Processing, Completed, Failed)                              │
│  - Output MP4 Video Repository (/app/videos)                                                   │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
├── alembic/                     # Database migration scripts and configuration
│   ├── env.py
│   └── versions/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── health.py        # Health check endpoint (/api/v1/health)
│       │   ├── progress.py      # WebSocket real-time progress endpoint (/ws/progress)
│       │   └── videos.py        # Video dispatch, audio preview streaming, listing & download
│       └── router.py            # API & WebSocket router aggregation
├── core/
│   ├── cache.py                 # Redis cache interface
│   ├── config.py                # Pydantic BaseSettings (App, DB, Redis, Celery, LLM)
│   ├── lifespan.py              # Hugging Face auth & Kokoro TTS model initialization
│   ├── logging.py               # Structured application logging
│   ├── security.py              # API key verification middleware
│   └── websocket.py             # ConnectionManager for client broadcasting
├── db/
│   ├── models/
│   │   └── videos_model.py      # SQLAlchemy VideoJob database model
│   ├── base.py                  # Declarative ORM Base
│   └── session.py               # Async Engine & Sessionmaker
├── frontend/
│   └── templates/
│       ├── index.html           # Web Studio dashboard UI
│       └── template.html        # HTML/CSS promo slide template with CSS keyframe animations
├── schemas/
│   └── app_schemas.py           # Pydantic request/response models
├── services/
│   ├── subtitle_service.py     # Subtitle HTML span generator with karaoke delays
│   ├── tts_service.py           # Gemini LLM copywriter & Kokoro voice synthesis
│   └── video_service.py        # Playwright recorder & FFmpeg sidechain audio ducking
├── workers/
│   ├── celery_app.py            # Celery application configuration
│   └── tasks.py                 # Asynchronous background video generation tasks
├── docker-compose.yaml          # Multi-container orchestration (Web, Worker, Redis)
├── Dockerfile                   # Playwright-enabled Ubuntu Jammy container setup
├── main.py                      # FastAPI app entry point & static file routing
└── requirements.txt             # Python dependencies
```

---
## 🚀 Getting Started

### Prerequisites

- **Docker** & **Docker Compose**
- *(Optional for bare-metal setup)* Python 3.11+, FFmpeg, eSpeak NG system packages

### Environment Configuration

1. Copy the example environment file:
   ```bash
   cp core/.env.example .env
   ```

2. Configure environment variables in `.env` or system environment:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Environment mode (`development`, `test`, `staging`, `production`) |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/videodb` | Async PostgreSQL DSN |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Celery broker URL |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/2` | Celery result backend URL |
| `GEMINI_API_KEY` | `""` | Google GenAI API Key for dynamic sales copywriting |
| `HF_TOKEN` | `""` | Hugging Face token for downloading Kokoro-82M TTS model |
| `API_KEY` | `""` | Optional API Key for securing API endpoints |

### Running the Application

Launch the microservice stack with Docker Compose:

```bash
docker compose up --build -d
```

The application services will be accessible at:
- **🎬 Web Studio Dashboard**: `http://localhost:8000/dashboard`
- **📡 API Root**: `http://localhost:8000/`
- **📖 Interactive API Docs (Swagger)**: `http://localhost:8000/docs`

To inspect application logs:
```bash
docker compose logs -f web worker
```

---
## 📡 API & WebSocket Specification

### REST Endpoints

#### 1. Trigger Video Generation
Dispatches a background video rendering job to the Celery worker.

- **URL**: `POST /api/v1/videos/generate`
- **Headers**: `x-api-key: <API_KEY>` (if configured)
- **Payload**:
```json
{
  "product_title": "Wireless Noise-Canceling Headphones",
  "price": 199.99,
  "image_url": "https://example.com/product.jpg",
  "voice_persona": "af_bella",
  "aspect_ratio": "9:16",
  "use_llm_script": true
}
```
- **Response**:
```json
{
  "status": "started",
  "task_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "message": "Video generation pipeline dispatched to Celery worker."
}
```

#### 2. Generate Audio Preview Stream
Generates a fast voiceover preview without rendering full video frames.

- **URL**: `POST /api/v1/videos/preview-audio`
- **Payload**:
```json
{
  "product_title": "Smart Watch Series 9",
  "price": 299.00,
  "image_url": "https://example.com/watch.jpg",
  "voice_persona": "am_adam"
}
```
- **Response**:
```json
{
  "status": "success",
  "voice_persona": "am_adam",
  "preview_url": "/api/v1/videos/preview-audio/stream/voice_preview_12345.wav"
}
```

#### 3. List Generated Videos
- **URL**: `GET /api/v1/videos`
- **Response**:
```json
{
  "count": 2,
  "videos": [
    {
      "filename": "product_custom_12345.mp4",
      "download_url": "/api/videos/download/product_custom_12345.mp4"
    }
  ]
}
```

#### 4. Download Video File
- **URL**: `GET /api/v1/videos/videos/download/{filename}`
- **Response**: Binary MP4 stream.

### WebSockets

- **URL**: `ws://localhost:8000/ws/progress`
- **Events**: Receives real-time updates during video generation (e.g., LLM copywriting, TTS synthesis, Playwright recording, FFmpeg sidechain ducking).

---

## 🎙️ Category Voice Persona Mapping

Products are automatically matched to specialized Kokoro voice personas based on product category:

| Category | Persona Key | Description |
| :--- | :--- | :--- |
| **Electronics** | `am_adam` | Deep, authoritative tech male voice |
| **Jewelry** | `af_bella` | Elegant, refined retail female voice |
| **Mens Clothing** | `am_michael` | Crisp, energetic male voice |
| **Womens Clothing** | `af_nicole` | Smooth, engaging female voice |

---

## 🎛️ FFmpeg Audio Ducking Pipeline

When a background music file is placed at `assets/bgm.mp3`, FFmpeg applies sidechain compression so the music automatically ducks during voiceover speech:

```bash
ffmpeg -y -i video.webm -i voiceover.wav -i bgm.mp3 \
  -filter_complex "[2:a]volume=0.2[bgm_base];[bgm_base][1:a]sidechaincompress=threshold=0.02:ratio=6:attack=10:release=250[bgm_ducked];[1:a][bgm_ducked]amix=inputs=2:duration=first[final_audio]" \
  -map 0:v -map "[final_audio]" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest output.mp4
```

---

## 🛠️ Database Migrations

Alembic manages database schema migrations in the database layer.

---

## 📄 License

This project is open-source under the MIT License.
