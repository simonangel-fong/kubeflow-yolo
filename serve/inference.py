"""
YOLO pre/post-processing for a bare ONNX graph.

Exporting to ONNX gives you the network and nothing else. Ultralytics' own
pre-processing (letterbox, BGR->RGB, /255, NCHW) and post-processing (confidence
filter, NMS, un-letterbox back to original pixels) are Python that stayed behind
in the .pt wrapper. This module is that half, rewritten against numpy so the
predictor needs neither torch nor ultralytics.

Getting this wrong is the usual reason a "working" exported model returns boxes
in the wrong place: a plain resize instead of a letterbox shifts every
coordinate, and the error is proportional to how far the aspect ratio is from 1.
"""

from __future__ import annotations

import numpy as np

# YOLO11 head emits (batch, 4 + num_classes, num_anchors): xywh then per-class
# scores. There is no separate objectness channel as in v5/v7.
BOX_CHANNELS = 4


def letterbox(image: np.ndarray, imgsz: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """
    Resize preserving aspect ratio, pad the remainder to a square.

    Returns (padded_image, scale, (pad_x, pad_y)) -- the scale and pads are what
    map predicted coordinates back onto the caller's original image.
    """
    height, width = image.shape[:2]
    scale = min(imgsz / height, imgsz / width)
    new_h, new_w = round(height * scale), round(width * scale)

    # cv2 is already present for image decoding; its INTER_LINEAR matches what
    # ultralytics uses, so exported and served results agree.
    import cv2

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_x, pad_y = (imgsz - new_w) // 2, (imgsz - new_h) // 2
    # 114 is the ultralytics padding value; the model saw it during training.
    canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, scale, (pad_x, pad_y)


def preprocess(image_bgr: np.ndarray, imgsz: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """BGR uint8 HWC -> normalized float32 NCHW, plus the geometry to undo it."""
    padded, scale, pads = letterbox(image_bgr, imgsz)
    rgb = padded[:, :, ::-1]                      # BGR -> RGB
    tensor = rgb.transpose(2, 0, 1).astype(np.float32) / 255.0   # HWC -> CHW
    return tensor[np.newaxis, ...], scale, pads   # add batch dim


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """Center form -> corner form."""
    xyxy = np.empty_like(boxes)
    half_w, half_h = boxes[:, 2] / 2, boxes[:, 3] / 2
    xyxy[:, 0] = boxes[:, 0] - half_w
    xyxy[:, 1] = boxes[:, 1] - half_h
    xyxy[:, 2] = boxes[:, 0] + half_w
    xyxy[:, 3] = boxes[:, 1] + half_h
    return xyxy


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """
    Greedy non-maximum suppression over corner-form boxes.

    Kept in numpy rather than pulled from torchvision -- it is twenty lines and
    it is the only thing that would otherwise drag torch into the image.
    """
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep: list[int] = []
    while order.size > 0:
        best = order[0]
        keep.append(int(best))
        if order.size == 1:
            break

        rest = order[1:]
        # Intersection of the best box with every remaining box.
        inter_x1 = np.maximum(x1[best], x1[rest])
        inter_y1 = np.maximum(y1[best], y1[rest])
        inter_x2 = np.minimum(x2[best], x2[rest])
        inter_y2 = np.minimum(y2[best], y2[rest])
        inter = (np.maximum(0.0, inter_x2 - inter_x1)
                 * np.maximum(0.0, inter_y2 - inter_y1))

        iou = inter / (areas[best] + areas[rest] - inter)
        order = rest[iou <= iou_threshold]

    return keep


def postprocess(
    output: np.ndarray,
    scale: float,
    pads: tuple[int, int],
    original_shape: tuple[int, int],
    names: list[str],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> list[dict]:
    """
    Raw ONNX output -> detections in the original image's pixel coordinates.

    `output` is (1, 4 + nc, anchors) as YOLO11 emits it.
    """
    predictions = output[0].T                     # (anchors, 4 + nc)
    boxes_xywh = predictions[:, :BOX_CHANNELS]
    class_scores = predictions[:, BOX_CHANNELS:]

    confidences = class_scores.max(axis=1)
    class_ids = class_scores.argmax(axis=1)

    # Drop the low-confidence anchors before NMS -- with 3549 anchors at 416px
    # this is what keeps the O(n^2) suppression cheap.
    mask = confidences >= conf_threshold
    if not mask.any():
        return []

    boxes = xywh_to_xyxy(boxes_xywh[mask])
    confidences, class_ids = confidences[mask], class_ids[mask]

    keep = nms(boxes, confidences, iou_threshold)
    boxes, confidences, class_ids = boxes[keep], confidences[keep], class_ids[keep]

    # Undo the letterbox: remove padding, then divide out the resize.
    pad_x, pad_y = pads
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / scale

    # A box may still poke outside the frame after rescaling; clip it.
    height, width = original_shape
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, width)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, height)

    return [
        {
            "class_id": int(class_id),
            "class_name": names[class_id] if class_id < len(names) else str(class_id),
            "confidence": round(float(confidence), 4),
            "box": {
                "x1": round(float(box[0]), 2),
                "y1": round(float(box[1]), 2),
                "x2": round(float(box[2]), 2),
                "y2": round(float(box[3]), 2),
            },
        }
        for box, confidence, class_id in zip(boxes, confidences, class_ids)
    ]
