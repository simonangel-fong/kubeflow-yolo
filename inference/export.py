"""
Export trained YOLO weights to ONNX, then verify the export before it ships.

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
import json
import shutil
import sys
from pathlib import Path

import yaml

# Repo root: inference/export.py -> inference -> repo
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

TRAIN_CFG = ROOT / "train-job" / "configs" / "train.yaml"
MODELS = ROOT / "models"
VAL_IMAGES = ROOT / "data" / "processed" / "val" / "images"

OPSET = 12

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
                        help="destination directory for the .onnx")
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


def output_stem(run: str, cfg: dict, imgsz: int) -> str:
    """
    Name the artifact after what produced it.

    A sweep already encodes images/epochs/imgsz in its run directory; a plain
    run does not, so spell it out from the config and the split on disk.
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
# export
# --------------------------------------------------------------------------

def export_onnx(weights: Path, imgsz: int) -> tuple[Path, list[str]]:
    """Export to ONNX. Returns (onnx_path, class_names)."""
    from ultralytics import YOLO

    model = YOLO(str(weights))
    # Class ids are the dict keys; sort so list index == class id.
    names = [model.names[i] for i in sorted(model.names)]

    exported = model.export(
        format="onnx",
        imgsz=imgsz,
        opset=OPSET,
        simplify=True,
        dynamic=False,   # fixed 1x3ximgszximgsz input
    )
    return Path(exported), names


def write_metadata(onnx_path: Path, imgsz: int, names: list[str]) -> Path:
    """The graph stores neither class names nor imgsz; the predictor needs both."""
    sidecar = onnx_path.with_suffix(".metadata.json")
    sidecar.write_text(json.dumps({"imgsz": imgsz, "names": names}, indent=2))
    return sidecar


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
    import numpy as np
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

    exported, names = export_onnx(weights, imgsz)

    args.out.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out / f"{output_stem(run, cfg, imgsz)}.onnx"
    shutil.move(str(exported), onnx_path)
    sidecar = write_metadata(onnx_path, imgsz, names)

    print(
        f"onnx        {onnx_path}  ({onnx_path.stat().st_size / 1e6:.1f} MB)")
    print(f"metadata    {sidecar.name}  {names}")

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
