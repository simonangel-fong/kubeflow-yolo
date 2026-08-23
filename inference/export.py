"""
Export trained YOLO weights into the serving artifact layout, then verify it.

The layout and the export live in src/artifact.py; this is the CLI over it,
plus the verification gate.

ONNX carries the network and nothing else: ultralytics' letterbox, NMS and
coordinate rescaling stay behind in the .pt wrapper and are reimplemented in
src/inference.py. That reimplementation fails silently -- boxes land in the
wrong place with no exception -- so the export is not finished until its
detections have been checked against the .pt they came from.

Usage:
    python -m inference.export                       # the run named in train.yaml
    python -m inference.export --run tune-cpu-556img-640px-ep20
    python -m inference.export --weights path/to/best.pt
    python -m inference.export --skip-verify         # export only, no gate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Repo root: inference/export.py -> inference -> repo
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.artifact import (OPSET, export_model, model_path,  # noqa: E402
                          read_metadata)

TRAIN_CFG = ROOT / "train-job" / "configs" / "train.yaml"
MODELS = ROOT / "models"
VAL_IMAGES = ROOT / "data" / "processed" / "val" / "images"

DEFAULT_MODEL_NAME = "yolo-plate-detector"

# Verification thresholds.
MAX_BOX_DELTA_PX = 2.0
VERIFY_IMAGES = 8
CONF, IOU = 0.25, 0.45


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """ Parse arguments. """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=TRAIN_CFG,
                        help="training config supplying imgsz, project and name")
    parser.add_argument("--run", default=None,
                        help="run directory under project/, defaults to the config's name")
    parser.add_argument("--weights", type=Path, default=None,
                        help="trained .pt to export; overrides --run")
    parser.add_argument("--out", type=Path, default=MODELS,
                        help="root of the model repository to write")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME,
                        help="model name; the directory served under --out")
    parser.add_argument("--skip-verify", action="store_true",
                        help="export without checking the result against the .pt")
    return parser.parse_args(argv)


# ##############################
# select
# ##############################
def resolve_weights(args: argparse.Namespace, cfg: dict) -> tuple[Path, str]:
    """Locate best.pt and the name of the run it came from."""
    if args.weights is not None:
        # <run>/weights/best.pt
        return args.weights, args.weights.parent.parent.name

    run = args.run or cfg["name"]
    project = Path(cfg["project"])
    project = project if project.is_absolute() else ROOT / project
    return project / run / "weights" / "best.pt", run


def run_label(run: str, cfg: dict, imgsz: int) -> str:
    """
    Describe what produced the artifact, for the metadata sidecar.

    A sweep already encodes images/epochs/imgsz in its run directory; a plain
    run does not.
    """
    if "img" in run:
        return run

    processed = ROOT / "data" / "processed"
    n_images = sum(
        len(list((processed / s / "images").iterdir()))
        for s in ("train", "val")
        if (processed / s / "images").is_dir()
    )
    return f"{run}-{n_images}img-{cfg['epochs']}ep-{imgsz}px"


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def verify(onnx_path: Path, weights: Path, imgsz: int, names: list[str]) -> bool:
    """
    Compare ONNX detections against the .pt on real images.

    Uses src/inference.py -- the same pre/post-processing the predictor runs --
    so a pass means the served path is correct, not merely that onnxruntime
    loaded the file.
    """
    import cv2
    import onnxruntime as ort
    from ultralytics import YOLO

    from src.inference import postprocess, preprocess

    images = sorted(VAL_IMAGES.iterdir())[
        :VERIFY_IMAGES] if VAL_IMAGES.is_dir() else []
    if not images:
        print(f"verify      SKIPPED, no images under {VAL_IMAGES}")
        return True

    session = ort.InferenceSession(str(onnx_path), providers=[
                                   "CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    reference = YOLO(str(weights))

    worst = 0.0
    mismatches = 0

    print(f"\n{'image':<34}{'onnx':>5}{'pt':>4}{'max_px':>9}{'d_conf':>9}")
    for image_path in images:
        image = cv2.imread(str(image_path))
        if image is None:
            continue

        # served path: letterbox -> graph -> NMS -> un-letterbox
        tensor, scale, pads = preprocess(image, imgsz)
        output = session.run(None, {input_name: tensor})[0]
        actual = postprocess(output, scale, pads,
                             image.shape[:2], names, CONF, IOU)

        # reference path
        expected = reference.predict(image_path, imgsz=imgsz, conf=CONF, iou=IOU,
                                     device="cpu", verbose=False)[0]
        exp_boxes = expected.boxes.xyxy.cpu().numpy()
        exp_confs = expected.boxes.conf.cpu().numpy()

        label = image_path.stem[:32]
        if len(actual) != len(exp_boxes):
            mismatches += 1
            print(
                f"{label:<34}{len(actual):>5}{len(exp_boxes):>4}{'COUNT MISMATCH':>18}")
            continue

        # both paths return detections ordered by confidence
        delta = d_conf = 0.0
        for det, box, conf in zip(actual, exp_boxes, exp_confs):
            corners = [det["box"][k] for k in ("x1", "y1", "x2", "y2")]
            delta = max(delta, max(abs(a - b) for a, b in zip(corners, box)))
            d_conf = max(d_conf, abs(det["confidence"] - float(conf)))

        worst = max(worst, delta)
        print(
            f"{label:<34}{len(actual):>5}{len(exp_boxes):>4}{delta:>9.2f}{d_conf:>9.4f}")

    ok = mismatches == 0 and worst <= MAX_BOX_DELTA_PX
    print(f"\nworst box delta  {worst:.2f} px (tolerance {MAX_BOX_DELTA_PX})")
    print(f"count mismatches {mismatches}")
    print("verify      PASS" if ok else "verify      FAIL")
    return ok


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.config.exists():
        raise SystemExit(f"no training config at {args.config}")
    cfg = yaml.safe_load(args.config.read_text())
    imgsz = cfg["imgsz"]

    weights, run = resolve_weights(args, cfg)
    if not weights.exists():
        raise SystemExit(f"no weights at {weights}")

    print(f"weights     {weights}")
    print(f"imgsz       {imgsz}")
    print(f"opset       {OPSET}")

    export_model(
        weights=weights,
        imgsz=imgsz,
        out_root=args.out,
        model_name=args.model_name,
        extra_meta={"run": run_label(run, cfg, imgsz)},
    )

    onnx_path = model_path(args.out, args.model_name)
    names = read_metadata(onnx_path)["names"]

    print(
        f"onnx        {onnx_path}  ({onnx_path.stat().st_size / 1e6:.1f} MB)")
    print(f"metadata    imgsz={imgsz} names={names}")

    if args.skip_verify:
        print("verify      SKIPPED")
        return 0

    if not verify(onnx_path, weights, imgsz, names):
        # Leave the files in place so the failure can be inspected, but fail
        # loudly: an unverified model must not be treated as shippable.
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
