"""
The model artifact layout, shared by the exporter and the predictor.

    <root>/<model_name>/
      config.pbtxt
      1/
        model.onnx
        metadata.json

Triton reads config.pbtxt and ignores metadata.json; the predictor reads
metadata.json and ignores config.pbtxt.

Imports stay light -- ultralytics is imported inside export_model -- so
src/model.py can import this at serving time.
"""

from __future__ import annotations

import json
from pathlib import Path

# onnxruntime in the Triton runtime rejects ultralytics' default opset 20
# with "Opset 20 is under development".
OPSET = 19

VERSION_DIR = "1"
MODEL_FILE = "model.onnx"
METADATA_FILE = "metadata.json"
CONFIG_FILE = "config.pbtxt"


# ##############################
# layout
# ##############################
def version_dir(root: Path, model_name: str) -> Path:
    """The directory holding model.onnx and metadata.json."""
    return Path(root) / model_name / VERSION_DIR


def model_path(root: Path, model_name: str) -> Path:
    return version_dir(root, model_name) / MODEL_FILE


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
# triton config
# ##############################
def build_config_pbtxt(onnx_path: Path, model_name: str) -> str:
    """
    Describe the graph from the graph itself rather than hardcoding shapes.

    max_batch_size is 0 because the export pins the batch dimension.
    """
    import onnx as onnx_mod

    graph = onnx_mod.load(str(onnx_path), load_external_data=False).graph
    nl = chr(10)

    def spec(value) -> str:
        dims = [
            d.dim_value if d.HasField("dim_value") else -1
            for d in value.type.tensor_type.shape.dim
        ]
        return nl.join([
            "  {",
            '    name: "' + value.name + '"',
            "    data_type: TYPE_FP32",
            "    dims: [" + ", ".join(str(d) for d in dims) + "]",
            "  }",
        ])

    return nl.join([
        'name: "' + model_name + '"',
        'platform: "onnxruntime_onnx"',
        "max_batch_size: 0",
        "input [",
        ("," + nl).join(spec(v) for v in graph.input),
        "]",
        "output [",
        ("," + nl).join(spec(v) for v in graph.output),
        "]",
        "",
    ])


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

    target = version_dir(out_root, model_name)
    target.mkdir(parents=True, exist_ok=True)

    onnx_path = target / MODEL_FILE
    shutil.move(str(exported), onnx_path)

    write_metadata(onnx_path, imgsz, names, opset=opset, extra=extra_meta)

    config = out_root / model_name / CONFIG_FILE
    config.write_text(build_config_pbtxt(onnx_path, model_name))

    return out_root
