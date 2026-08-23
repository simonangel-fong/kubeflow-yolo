"""
Call the served model and decode its output into plate boxes.

    python predict.py path/to/car.jpeg
    python predict.py car.jpeg --conf 0.4 --host <service>:8000

Triton returns YOLO's raw output tensor, not detections: NMS and the box
decode live in ultralytics, not in the ONNX graph. Anything calling this
endpoint has to do what this script does.

The pre/post-processing is imported from inference/src/inference.py: a
letterbox that pads differently from the one the export was verified against
puts boxes in the wrong place with no error.

Run from inside the cluster -- the predictor is a ClusterIP service.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

# Repo root: kubeflow/serving/predict.py -> serving -> kubeflow -> repo
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "inference"))

from src.inference import postprocess, preprocess  # noqa: E402

MODEL = "yolo-plate-detector"
HOST = "yolo-plate-detector-predictor.kubeflow-user-example-com.svc.cluster.local:8000"
IMGSZ = 640


def infer(host: str, blob: np.ndarray) -> np.ndarray:
    """POST the tensor to Triton's v2 endpoint and return the raw output."""
    payload = json.dumps({
        "inputs": [{
            "name": "images",
            "shape": list(blob.shape),
            "datatype": "FP32",
            "data": blob.flatten().tolist(),
        }]
    }).encode()

    url = f"http://{host}/v2/models/{MODEL}/infer"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)

    out = result["outputs"][0]
    return np.array(out["data"], dtype=np.float32).reshape(out["shape"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--imgsz", type=int, default=IMGSZ)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--names", nargs="*", default=["plate"],
                        help="class names, in class-id order")
    args = parser.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        raise SystemExit(f"cannot read {args.image}")

    blob, scale, pads = preprocess(image, args.imgsz)
    tensor = infer(args.host, blob)

    detections = postprocess(tensor, scale, pads, image.shape[:2],
                             args.names, args.conf, args.iou)

    height, width = image.shape[:2]
    print(f"{args.image}  {width}x{height}  {len(detections)} plate(s)")
    for d in detections:
        box = d["box"]
        print(f"  {d['class_name']}  conf {d['confidence']:.3f}  "
              f"xyxy [{box['x1']}, {box['y1']}, {box['x2']}, {box['y2']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
