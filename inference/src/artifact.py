"""
The model artifact layout, shared by the exporter and the predictor.

    <root>/<model_name>/
      model.onnx
      metadata.json

The graph carries neither class names nor imgsz, so metadata.json sits beside
it and the predictor resolves it by exact path.

Imports stay light -- ultralytics is imported inside export_model -- so
src/model.py can import this at serving time.
"""

from __future__ import annotations

import json
from pathlib import Path

# onnxruntime rejects ultralytics' default opset 20 with
# "Opset 20 is under development".
OPSET = 19

MODEL_FILE = "model.onnx"
METADATA_FILE = "metadata.json"


# ##############################
# layout
# ##############################
def model_path(root: Path, model_name: str) -> Path:
    return Path(root) / model_name / MODEL_FILE


def metadata_path(onnx_path: Path) -> Path:
    """The sidecar beside a model.onnx, by exact path -- never by glob."""
    return Path(onnx_path).parent / METADATA_FILE


# ##############################
# metadata
# ##############################
def write_metadata(onnx_path: Path, imgsz: int, names: list[str],
                   opset: int = OPSET, extra: dict | None = None) -> Path:
    """
    The graph carries neither class names nor imgsz; the predictor needs both.

    `extra` records provenance (run_id, mAP50), which nothing reads at
    inference time.
    """
    meta = {"imgsz": int(imgsz), "names": list(names), "opset": int(opset)}
    meta.update(extra or {})

    sidecar = metadata_path(onnx_path)
    sidecar.write_text(json.dumps(meta, indent=2))
    return sidecar


def read_metadata(onnx_path: Path) -> dict:
    """The sidecar's contents, or {} when there is none."""
    sidecar = metadata_path(onnx_path)
    if not sidecar.exists():
        return {}
    return json.loads(sidecar.read_text())


# ##############################
# export
# ##############################
def export_model(
    weights: Path,
    imgsz: int,
    out_root: Path,
    model_name: str,
    names: list[str] | None = None,
    opset: int = OPSET,
    extra_meta: dict | None = None,
) -> Path:
    """
    Export trained .pt weights into the artifact layout. Returns out_root.

    `names` overrides the class names baked into the .pt, so the pipeline can
    label with the dataset's classes.txt.
    """
    import shutil

    from ultralytics import YOLO

    weights, out_root = Path(weights), Path(out_root)

    model = YOLO(str(weights))
    if names is None:
        # Class ids are the dict keys; sort so list index == class id.
        names = [model.names[i] for i in sorted(model.names)]

    exported = model.export(
        format="onnx",
        imgsz=imgsz,
        opset=opset,
        simplify=True,
        dynamic=False,   # fixed 1x3ximgszximgsz input
    )

    onnx_path = model_path(out_root, model_name)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(exported), onnx_path)

    write_metadata(onnx_path, imgsz, names, opset=opset, extra=extra_meta)

    return out_root
