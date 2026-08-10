"""
KServe-compatible predictor for the exported YOLO ONNX model.

Speaks the KServe V1 protocol so the InferenceService needs no transformer:

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
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from serve.inference import postprocess, preprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yolo-predictor")

# KServe mounts whatever storageUri resolves to at /mnt/models.
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/mnt/models"))
MODEL_NAME = os.environ.get("MODEL_NAME", "yolo-car-plate")

CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.45"))

# Cap decoded image bytes so one oversized request cannot exhaust the pod's
# memory limit. 10 MB comfortably covers a phone photo.
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", 10 * 1024 * 1024))

app = FastAPI(title="YOLO car-plate predictor")

# Populated by startup(); module-level so handlers can reach them.
session: ort.InferenceSession | None = None
input_name: str = ""
imgsz: int = 416
class_names: list[str] = []


def find_model(model_dir: Path) -> Path:
    """
    Locate the .onnx under the mount.

    MLflow's storage initializer lands the artifact one or two directories
    down (model/, or model/data/), so a plain join is not enough.
    """
    direct = model_dir / "model.onnx"
    if direct.exists():
        return direct

    candidates = sorted(model_dir.rglob("*.onnx"))
    if not candidates:
        raise FileNotFoundError(f"no .onnx under {model_dir}")
    if len(candidates) > 1:
        logger.warning("multiple .onnx found, using %s", candidates[0])
    return candidates[0]


def load_metadata(onnx_path: Path) -> tuple[int, list[str]]:
    """
    Read imgsz and class names written alongside the model by serve/export.py.

    Falls back to the graph's own input shape and positional class names, so a
    model exported without the sidecar still serves -- just with unlabelled
    classes.
    """
    # Direct match first: a PVC or bind mount keeps the exporter's filenames.
    sidecar = onnx_path.with_suffix(".metadata.json")
    if not sidecar.exists():
        # MLflow renames the model to model.onnx but logs the sidecar under its
        # original stem, so the names no longer line up. Any one in the
        # directory describes this model -- only one is ever logged.
        siblings = sorted(onnx_path.parent.glob("*.metadata.json"))
        if siblings:
            sidecar = siblings[0]

    if sidecar.exists():
        meta = json.loads(sidecar.read_text())
        logger.info("metadata from %s", sidecar.name)
        return int(meta["imgsz"]), list(meta["names"])

    logger.warning("no metadata sidecar beside %s, inferring from graph", onnx_path.name)
    return 0, []


@app.on_event("startup")
def startup() -> None:
    global session, input_name, imgsz, class_names

    onnx_path = find_model(MODEL_DIR)
    logger.info("loading %s", onnx_path)

    session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"],
    )
    spec = session.get_inputs()[0]
    input_name = spec.name

    imgsz, class_names = load_metadata(onnx_path)
    if not imgsz:
        # Static export shape is (1, 3, H, W); H is the trained imgsz.
        imgsz = int(spec.shape[2])
    if not class_names:
        num_classes = session.get_outputs()[0].shape[1] - 4
        class_names = [str(i) for i in range(num_classes)]

    logger.info("ready: imgsz=%d classes=%s", imgsz, class_names)


class PredictRequest(BaseModel):
    instances: list[dict[str, Any]]


def decode_image(instance: dict[str, Any]) -> np.ndarray:
    """Pull base64 image bytes out of a KServe V1 instance and decode to BGR."""
    import cv2

    image_field = instance.get("image")
    if isinstance(image_field, dict):
        payload = image_field.get("b64")
    elif isinstance(image_field, str):
        payload = image_field
    else:
        payload = None

    if not payload:
        raise HTTPException(400, "instance must carry image.b64 (base64 string)")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, f"image.b64 is not valid base64: {exc}") from exc

    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"image exceeds {MAX_IMAGE_BYTES} bytes")

    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "could not decode image; expected jpeg or png")
    return image


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models/{name}")
def model_ready(name: str) -> dict[str, Any]:
    """KServe readiness probe. 503 until the session exists."""
    if name != MODEL_NAME:
        raise HTTPException(404, f"model {name} not found")
    if session is None:
        raise HTTPException(503, "model not loaded")
    return {"name": name, "ready": True}


@app.post("/v1/models/{name}:predict")
def predict(name: str, request: PredictRequest) -> dict[str, Any]:
    if name != MODEL_NAME:
        raise HTTPException(404, f"model {name} not found")
    if session is None:
        raise HTTPException(503, "model not loaded")
    if not request.instances:
        raise HTTPException(400, "instances must not be empty")

    predictions = []
    for instance in request.instances:
        image = decode_image(instance)

        tensor, scale, pads = preprocess(image, imgsz)
        output = session.run(None, {input_name: tensor})[0]

        detections = postprocess(
            output,
            scale=scale,
            pads=pads,
            original_shape=image.shape[:2],
            names=class_names,
            conf_threshold=float(instance.get("conf", CONF_THRESHOLD)),
            iou_threshold=float(instance.get("iou", IOU_THRESHOLD)),
        )
        predictions.append({
            "detections": detections,
            "count": len(detections),
        })

    return {"predictions": predictions}
