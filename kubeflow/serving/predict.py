"""
Call the served model and decode its output into plate boxes.

    python predict.py path/to/car.jpeg
    python predict.py car.jpeg --conf 0.4 --host <service>:8000

Triton returns YOLO's raw output tensor, not detections: NMS and the box
decode live in ultralytics, not in the ONNX graph. Anything calling this
endpoint has to do what this script does.

Run from inside the cluster -- the predictor is a ClusterIP service.
"""

from __future__ import annotations

import argparse
import json
import urllib.request

import cv2
import numpy as np

MODEL = "yolo-plate-detector"
HOST = "yolo-plate-detector-predictor.kubeflow-user-example-com.svc.cluster.local:8000"
IMGSZ = 640


def preprocess(path: str) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Letterbox to IMGSZ, keeping aspect ratio, and scale to 0-1 CHW."""
    image = cv2.imread(path)
    if image is None:
        raise SystemExit(f"cannot read {path}")

    height, width = image.shape[:2]
    scale = min(IMGSZ / height, IMGSZ / width)
    resized = cv2.resize(image, (int(width * scale), int(height * scale)))

    # pad to a square canvas; the model was exported at a fixed 640x640
    canvas = np.full((IMGSZ, IMGSZ, 3), 114, dtype=np.uint8)
    canvas[: resized.shape[0], : resized.shape[1]] = resized

    blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return blob.transpose(2, 0, 1)[None], scale, (height, width)


def decode(output: np.ndarray, scale: float, conf_threshold: float) -> list[dict]:
    """Turn the raw [1, 4+nc, 8400] tensor into boxes in original-image space."""
    # -> (8400, 4 + nc): one row per candidate, xywh then per-class scores
    predictions = output[0].T

    scores = predictions[:, 4:].max(axis=1)
    keep = scores > conf_threshold
    predictions, scores = predictions[keep], scores[keep]
    if not len(predictions):
        return []

    # cxcywh -> xywh corners, undoing the letterbox scale
    boxes = predictions[:, :4].copy()
    boxes[:, 0] -= boxes[:, 2] / 2
    boxes[:, 1] -= boxes[:, 3] / 2
    boxes /= scale

    # the graph emits every candidate; overlapping duplicates are removed here
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf_threshold, 0.45)
    if len(indices) == 0:
        return []

    return [
        {
            "box": [round(float(v), 1) for v in boxes[i]],
            "confidence": round(float(scores[i]), 4),
        }
        for i in np.array(indices).flatten()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    blob, scale, (height, width) = preprocess(args.image)

    payload = json.dumps({
        "inputs": [{
            "name": "images",
            "shape": list(blob.shape),
            "datatype": "FP32",
            "data": blob.flatten().tolist(),
        }]
    }).encode()

    url = f"http://{args.host}/v2/models/{MODEL}/infer"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)

    out = result["outputs"][0]
    tensor = np.array(out["data"], dtype=np.float32).reshape(out["shape"])

    detections = decode(tensor, scale, args.conf)
    print(f"{args.image}  {width}x{height}  {len(detections)} plate(s)")
    for d in detections:
        x, y, w, h = d["box"]
        print(f"  conf {d['confidence']:.3f}  xywh [{x}, {y}, {w}, {h}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
