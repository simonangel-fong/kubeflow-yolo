"""
FastAPI to serve YOLO model with ONNX.

Endpionts:
    GET  /v1/models/{name}            readiness, as KServe probes it
    POST /v1/models/{name}:predict    {"instances": [{"image": {"b64": "..."}}]}
    GET  /healthz                     liveness

The model is loaded once at startup; onnxruntime sessions are thread-safe for
inference, so the single session serves every request.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.inference import postprocess, preprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yolo-predictor")

# model mount point
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/mnt/models"))
# model name
MODEL_NAME = os.environ.get("MODEL_NAME", "yolo-car-plate")

CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.45"))

# Cap decoded image bytes so one oversized request cannot exhaust the pod's
# memory limit. 10 MB comfortably covers a phone photo.
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", 10 * 1024 * 1024))


@dataclass
class Model:
    """Everything loaded from disk, in one place rather than four globals."""

    session: ort.InferenceSession | None = None
    input_name: str = ""
    imgsz: int = 0
    names: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.session is not None


model = Model()


def find_model(model_dir: Path) -> Path:
    """
    Locate the .onnx under the mount.

    A bind mount or PVC keeps the exporter's filename; MLflow's storage
    initializer renames it to model.onnx and may nest it a directory or two
    down. Both layouts have to resolve.
    """
    direct = model_dir / "model.onnx"
    if direct.exists():
        return direct

    candidates = sorted(model_dir.rglob("*.onnx"))
    if not candidates:
        raise FileNotFoundError(f"no .onnx under {model_dir}")
    if len(candidates) > 1:
        logger.warning("%d .onnx found, using %s",
                       len(candidates), candidates[0].name)
    return candidates[0]


def load_metadata(onnx_path: Path) -> tuple[int, list[str]]:
    """
    Read imgsz and class names written alongside the model by inference/export.py.

    Returns (0, []) when there is no sidecar; the caller falls back to the
    graph itself so a model exported without one still serves, just with
    unlabelled classes.
    """
    sidecar = onnx_path.with_suffix(".metadata.json")
    if not sidecar.exists():
        # MLflow renames the model to model.onnx but logs the sidecar under its
        # original stem, so the two no longer line up. Only one is ever logged.
        siblings = sorted(onnx_path.parent.glob("*.metadata.json"))
        if siblings:
            sidecar = siblings[0]

    if not sidecar.exists():
        logger.warning("no metadata sidecar beside %s", onnx_path.name)
        return 0, []

    meta = json.loads(sidecar.read_text())
    logger.info("metadata from %s", sidecar.name)
    return int(meta["imgsz"]), list(meta["names"])


def load() -> None:
    """
    Populate the module-level model.

    A failure here is recorded rather than raised: the process stays up so the
    readiness probe can report *why* it is not ready. Exiting instead gives a
    crash-looping pod whose cause is only visible in scrollback.
    """
    try:
        onnx_path = find_model(MODEL_DIR)
        logger.info("loading %s", onnx_path)

        session = ort.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"])
        spec = session.get_inputs()[0]

        imgsz, names = load_metadata(onnx_path)
        if not imgsz:
            # Static export shape is (1, 3, H, W); H is the trained imgsz.
            imgsz = int(spec.shape[2])
        if not names:
            num_classes = session.get_outputs()[0].shape[1] - 4
            names = [str(i) for i in range(num_classes)]

        model.session = session
        model.input_name = spec.name
        model.imgsz = imgsz
        model.names = names
        logger.info("ready: imgsz=%d classes=%s", imgsz, names)

    except Exception as exc:  # noqa: BLE001 - surfaced through /v1/models/{name}
        model.error = f"{type(exc).__name__}: {exc}"
        logger.error("model load failed: %s", model.error)


@asynccontextmanager
async def lifespan(_: FastAPI):
    load()
    yield


app = FastAPI(title="YOLO car-plate predictor", lifespan=lifespan)


class PredictRequest(BaseModel):
    instances: list[dict[str, Any]]


def decode_image(instance: dict[str, Any]) -> np.ndarray:
    """Pull base64 image bytes out of a KServe V1 instance and decode to BGR."""
    image_field = instance.get("image")
    if isinstance(image_field, dict):
        payload = image_field.get("b64")
    elif isinstance(image_field, str):
        payload = image_field
    else:
        payload = None

    if not payload:
        raise HTTPException(
            400, "instance must carry image.b64 (base64 string)")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            400, f"image.b64 is not valid base64: {exc}") from exc

    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"image exceeds {MAX_IMAGE_BYTES} bytes")

    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            400, "could not decode image; expected jpeg or png")
    return image


def require_model(name: str) -> None:
    """Guard shared by both model routes."""
    if name != MODEL_NAME:
        raise HTTPException(404, f"model {name} not found")
    if not model.ready:
        raise HTTPException(503, model.error or "model not loaded")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness. Answers even when the model failed to load."""
    return {"status": "ok"}


@app.get("/v1/models/{name}")
def model_ready(name: str) -> dict[str, Any]:
    """KServe readiness probe. 503 with the load error until the model is up."""
    require_model(name)
    return {
        "name": name,
        "ready": True,
        "imgsz": model.imgsz,
        "classes": model.names,
    }


@app.post("/v1/models/{name}:predict")
def predict(name: str, request: PredictRequest) -> dict[str, Any]:
    """Predict"""
    require_model(name)
    if not request.instances:
        raise HTTPException(400, "instances must not be empty")

    predictions = []
    for instance in request.instances:
        image = decode_image(instance)

        tensor, scale, pads = preprocess(image, model.imgsz)
        output = model.session.run(None, {model.input_name: tensor})[0]

        detections = postprocess(
            output,
            scale=scale,
            pads=pads,
            original_shape=image.shape[:2],
            names=model.names,
            # per-request overrides, so a caller can tune without a redeploy
            conf_threshold=float(instance.get("conf", CONF_THRESHOLD)),
            iou_threshold=float(instance.get("iou", IOU_THRESHOLD)),
        )
        predictions.append({"detections": detections,
                           "count": len(detections)})

    return {"predictions": predictions}
