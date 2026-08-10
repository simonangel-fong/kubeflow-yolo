"""
Export trained YOLO weights to ONNX and register them in MLflow.

The .pt from ultralytics carries the whole torch stack with it. ONNX drops
that dependency at serving time: onnxruntime alone is enough, which keeps the
predictor image small enough to be worth pulling onto a kind node.

Usage:
    python -m serve.export                              # runs/local-train/weights/best.pt
    python -m serve.export --weights path/to/best.pt
    python -m serve.export --no-register                # export only, skip mlflow
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Repo root: serve/export.py -> serve -> repo
ROOT = Path(__file__).resolve().parent.parent

DEFAULT_WEIGHTS = ROOT / "runs" / "local-train" / "weights" / "best.pt"
DEFAULT_MODEL_NAME = "yolo-car-plate"

# Must match training. A mismatch here does not error -- it silently costs
# accuracy, because the letterbox in serve/app.py resizes to the wrong grid.
DEFAULT_IMGSZ = 416


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS,
                        help="trained .pt to export")
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ,
                        help="must match the training imgsz")
    parser.add_argument("--opset", type=int, default=12)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME,
                        help="registered model name in mlflow")
    parser.add_argument("--no-register", action="store_true",
                        help="write the .onnx but do not touch mlflow")
    return parser.parse_args(argv)


def export_onnx(weights: Path, imgsz: int, opset: int) -> tuple[Path, list[str]]:
    """Export to ONNX. Returns (onnx_path, class_names)."""
    from ultralytics import YOLO

    model = YOLO(str(weights))
    # Class names live in the checkpoint; the ONNX graph does not carry them,
    # so they have to travel to the predictor as separate metadata.
    names = [model.names[i] for i in sorted(model.names)]

    exported = model.export(
        format="onnx",
        imgsz=imgsz,
        opset=opset,
        simplify=True,
        dynamic=False,
    )
    return Path(exported), names


def register(onnx_path: Path, model_name: str, meta: dict) -> str:
    """Log the ONNX to mlflow and cut a registered version. Returns model_uri."""
    import mlflow
    import onnx

    model = onnx.load(str(onnx_path))

    with mlflow.start_run(run_name=f"export-{onnx_path.stem}") as run:
        mlflow.log_params(meta)
        mlflow.onnx.log_model(
            onnx_model=model,
            name="model",
            registered_model_name=model_name,
            # Ultralytics has already baked the input shape into the graph;
            # onnxruntime is the only consumer, so skip the pyfunc wrapper's
            # inference and keep the artifact to just the graph.
            save_as_external_data=False,
            metadata=meta,
        )
        return f"runs:/{run.info.run_id}/model"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.weights.exists():
        raise SystemExit(f"no weights at {args.weights}")

    onnx_path, names = export_onnx(args.weights, args.imgsz, args.opset)
    size_mb = onnx_path.stat().st_size / 1e6
    print(f"exported    {onnx_path}  ({size_mb:.1f} MB)")
    print(f"classes     {names}")

    meta = {
        "imgsz": args.imgsz,
        "opset": args.opset,
        "classes": json.dumps(names),
        "source_weights": str(args.weights.relative_to(ROOT)),
    }

    # The predictor reads this next to the .onnx to label its boxes.
    sidecar = onnx_path.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps({"imgsz": args.imgsz, "names": names}, indent=2))
    print(f"metadata    {sidecar}")

    if args.no_register:
        return 0

    model_uri = register(onnx_path, args.model_name, meta)
    print(f"registered  {args.model_name} <- {model_uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
