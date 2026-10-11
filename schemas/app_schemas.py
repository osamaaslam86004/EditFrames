from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal


class VideoGenerateRequest(BaseModel):
    product_title: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    image_url: str
    voice_persona: Literal["af_bella", "am_adam", "am_michael", "af_nicole"] = (
        "af_bella"
    )
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    use_llm_script: bool = True


class VideoJobResponse(BaseModel):
    id: str
    product_title: str
    status: str
    output_url: str | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}
