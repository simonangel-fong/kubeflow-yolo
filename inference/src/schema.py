"""
Request shapes for the KServe V1 protocol, and decoding them to images.

    {"instances": [{"image": {"b64": "..."}, "conf": 0.4}]}

Validation lives here so the route handlers stay to routing.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel

from src.config import MAX_IMAGE_BYTES


class PredictRequest(BaseModel):
    instances: list[dict[str, Any]]


class DecodeError(ValueError):
    """Bad input from the caller. Carries the HTTP status the route should send."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def decode_image(instance: dict[str, Any]) -> np.ndarray:
    """
    Pull base64 image bytes out of a V1 instance and decode to a BGR array.

    Accepts both {"image": {"b64": ...}} and the flatter {"image": "..."}.
    """
    image_field = instance.get("image")
    if isinstance(image_field, dict):
        payload = image_field.get("b64")
    elif isinstance(image_field, str):
        payload = image_field
    else:
        payload = None

    if not payload:
        raise DecodeError(400, "instance must carry image.b64 (base64 string)")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DecodeError(400, f"image.b64 is not valid base64: {exc}") from exc

    if len(raw) > MAX_IMAGE_BYTES:
        raise DecodeError(413, f"image exceeds {MAX_IMAGE_BYTES} bytes")

    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise DecodeError(400, "could not decode image; expected jpeg or png")
    return image
