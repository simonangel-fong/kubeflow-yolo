"""
The ONNX model: locating it, loading it, running it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import onnxruntime as ort

from src.inference import postprocess, preprocess

# logger
logger = logging.getLogger("yolo-predictor.model")

# YOLO11 head emits (batch, 4 + num_classes, anchors); the 4 are box channels.
BOX_CHANNELS = 4


def find_model(model_dir: Path) -> Path:
    """
    Locate the .onnx under the mount.
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
    Read imgsz and class names written alongside the model by export.py.

    Returns (0, []) when there is no sidecar; the caller falls back to the
    graph itself, so a model exported without one still serves -- just with
    unlabelled classes.
    """
    sidecar = onnx_path.with_suffix(".metadata.json")
    if not sidecar.exists():
        siblings = sorted(onnx_path.parent.glob("*.metadata.json"))
        if siblings:
            sidecar = siblings[0]

    if not sidecar.exists():
        logger.warning("no metadata sidecar beside %s", onnx_path.name)
        return 0, []

    meta = json.loads(sidecar.read_text())
    logger.info("metadata from %s", sidecar.name)
    return int(meta["imgsz"]), list(meta["names"])


@dataclass
class Detector:
    """
    A loaded ONNX model and the metadata needed to interpret its output.
    """

    session: ort.InferenceSession | None = None
    input_name: str = ""
    imgsz: int = 0
    names: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ready(self) -> bool:
        return self.session is not None

    def load(self, model_dir: Path) -> None:
        """Populate from the .onnx under model_dir. Records failures, never raises."""
        try:
            onnx_path = find_model(model_dir)
            logger.info("loading %s", onnx_path)

            session = ort.InferenceSession(
                str(onnx_path), providers=["CPUExecutionProvider"])
            spec = session.get_inputs()[0]

            imgsz, names = load_metadata(onnx_path)
            if not imgsz:
                # Static export shape is (1, 3, H, W); H is the trained imgsz.
                imgsz = int(spec.shape[2])
            if not names:
                num_classes = session.get_outputs()[0].shape[1] - BOX_CHANNELS
                names = [str(i) for i in range(num_classes)]

            self.session = session
            self.input_name = spec.name
            self.imgsz = imgsz
            self.names = names
            self.error = ""
            logger.info("ready: imgsz=%d classes=%s", imgsz, names)

        except Exception as exc:  # noqa: BLE001 - surfaced through readiness
            self.error = f"{type(exc).__name__}: {exc}"
            logger.error("model load failed: %s", self.error)

    def predict(
        self,
        image_bgr: np.ndarray,
        conf_threshold: float,
        iou_threshold: float,
    ) -> list[dict]:
        """
        Detections for one BGR image, in that image's pixel coordinates.

        letterbox -> graph -> NMS -> un-letterbox. The pre/post-processing is
        the half of inference that ONNX export leaves behind.
        """
        if self.session is None:
            raise RuntimeError(self.error or "model not loaded")

        tensor, scale, pads = preprocess(image_bgr, self.imgsz)
        output = self.session.run(None, {self.input_name: tensor})[0]

        return postprocess(
            output,
            scale=scale,
            pads=pads,
            original_shape=image_bgr.shape[:2],
            names=self.names,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
        )
