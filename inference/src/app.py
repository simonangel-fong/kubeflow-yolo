"""
FastAPI endpoints for the YOLO ONNX predictor.
    GET  /healthz                     liveness
    GET  /v1/models/{name}            readiness, as KServe probes it
    POST /v1/models/{name}:predict    {"instances": [{"image": {"b64": "..."}}]}
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from src.config import CONF_THRESHOLD, IOU_THRESHOLD, MODEL_DIR, MODEL_NAME
from src.model import Detector
from src.schema import DecodeError, PredictRequest, decode_image

# logging
logging.basicConfig(level=logging.INFO)

# construct detector per onnxruntime session
detector = Detector()


# lifespan
@asynccontextmanager
async def lifespan(_: FastAPI):
    detector.load(MODEL_DIR)
    yield


# construct fastapi
app = FastAPI(title="YOLO car-plate predictor", lifespan=lifespan)


def require_model(name: str) -> None:
    """Guard shared by both model routes."""
    if name != MODEL_NAME:
        raise HTTPException(404, f"model {name} not found")
    if not detector.ready:
        raise HTTPException(503, detector.error or "model not loaded")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness."""
    return {"status": "ok"}


@app.get("/v1/models/{name}")
def model_ready(name: str) -> dict[str, Any]:
    """Readiness. 200 when model is up; otherwise, 503."""
    require_model(name)
    return {
        "name": name,
        "ready": True,
        "imgsz": detector.imgsz,
        "classes": detector.names,
    }


@app.post("/v1/models/{name}:predict")
def predict(name: str, request: PredictRequest) -> dict[str, Any]:
    """Detections for each instance, in the original image's coordinates."""
    require_model(name)
    if not request.instances:
        raise HTTPException(400, "instances must not be empty")

    predictions = []
    for instance in request.instances:
        try:
            image = decode_image(instance)
        except DecodeError as exc:
            raise HTTPException(exc.status, exc.detail) from exc

        detections = detector.predict(
            image,
            # per-request overrides, so a caller can tune without a redeploy
            conf_threshold=float(instance.get("conf", CONF_THRESHOLD)),
            iou_threshold=float(instance.get("iou", IOU_THRESHOLD)),
        )
        predictions.append({"detections": detections,
                            "count": len(detections)})

    return {"predictions": predictions}
