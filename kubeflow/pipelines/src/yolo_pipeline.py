"""
KFP pipeline:
    prepare_data -> train -> evaluate -> register_model

Pipeline compiled with compile.py
"""

from kfp import dsl
from kfp.dsl import Metrics, Output

# allow k8s in with kfp
from kfp import kubernetes


# ##############################
# Pipeline step: prepare_data
# ##############################
@dsl.component(base_image="python:3.12", packages_to_install=["boto3", "pyyaml"])
def prepare_data(
    bucket: str,
    dvc_dir_hash: str,
    region: str,
    prefix: str,
    val_fraction: float,
    split_seed: int,
) -> str:
    import json
    import random
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    import boto3
    import yaml

    s3 = boto3.client("s3", region_name=region)

    # get dvc data
    def dvc_key(md5: str) -> str:
        return "dvcstore/files/md5/" + md5[:2] + "/" + md5[2:]

    manifest = json.loads(
        s3.get_object(Bucket=bucket, Key=dvc_key(dvc_dir_hash))["Body"].read()
    )
    by_relpath = {e["relpath"]: e["md5"] for e in manifest}

    suffixes = {".jpeg", ".jpg", ".png"}
    # images and labels pair by basename: foo.jpeg <-> foo.txt
    images = {Path(r).stem: r for r in by_relpath
              if Path(r).suffix.lower() in suffixes}

    stems = sorted(images)
    # random seeded
    random.Random(split_seed).shuffle(stems)
    cut = int(len(stems) * (1 - val_fraction))

    def copy(args):
        """Server-side copy: the object never travels through this pod."""
        src_key, dst_key = args
        s3.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": src_key},
            Key=dst_key,
        )

    jobs = []
    counts = {}
    for split, names in (("train", stems[:cut]), ("val", stems[cut:])):
        for stem in names:
            image = images[stem]
            jobs.append((dvc_key(by_relpath[image]),
                         prefix + "/" + split + "/images/" + Path(image).name))
            label = stem + ".txt"
            # an image with no label file is a legitimate negative sample
            if label in by_relpath:
                jobs.append((dvc_key(by_relpath[label]),
                             prefix + "/" + split + "/labels/" + label))
        counts[split] = len(names)

    if not counts["train"] or not counts["val"]:
        raise RuntimeError("empty split: " + str(counts))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(copy, jobs))

    class_names = (
        s3.get_object(Bucket=bucket, Key=dvc_key(
            by_relpath["classes.txt"]))["Body"]
        .read().decode().split()
    )
    # `path` is filled in by the training step, which knows its local download dir
    s3.put_object(
        Bucket=bucket,
        Key=prefix + "/data.yaml",
        Body=yaml.safe_dump(
            {
                "train": "train/images",
                "val": "val/images",
                "nc": len(class_names),
                "names": class_names,
            },
            sort_keys=False,
        ).encode(),
    )

    uri = "s3://" + bucket + "/" + prefix
    print("split", counts, "classes", class_names, "->", uri)
    return uri


# ##############################
# Pipeline step: train
# ##############################
@dsl.component(
    base_image="python:3.12",
    packages_to_install=["ultralytics-opencv-headless", "boto3", "pyyaml"],
)
def train(
    processed_uri: str,
    region: str,
    prefix: str,
    run_id: str,
    epochs: int,
    batch: int,
    imgsz: int,
    weights: str,
    device: str,
) -> str:
    import os
    from pathlib import Path

    import boto3
    import yaml

    # env var
    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    from ultralytics import YOLO

    bucket, _, data_prefix = processed_uri.removeprefix("s3://").partition("/")
    s3 = boto3.client("s3", region_name=region)

    # pull the split down to a local directory
    root = Path("/tmp/data")
    pages = s3.get_paginator("list_objects_v2")
    for page in pages.paginate(Bucket=bucket, Prefix=data_prefix + "/"):
        for obj in page.get("Contents", []):
            relative = obj["Key"][len(data_prefix) + 1:]
            if not relative or relative.endswith("/"):
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(target))

    # configure data config file
    data_yaml = root / "data.yaml"
    cfg = yaml.safe_load(data_yaml.read_text())
    cfg["path"] = str(root)
    data_yaml.write_text(yaml.safe_dump(cfg, sort_keys=False))

    # ##############################
    # train
    # ##############################
    results = YOLO(weights).train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        workers=4 if device != "cpu" else 2,
        project="/tmp/runs",
        name="train",
        exist_ok=True,
        plots=False,
    )

    # output
    best = Path(results.save_dir) / "weights" / "best.pt"
    key = prefix.rstrip("/") + "/" + run_id + "/train/best.pt"
    s3.upload_file(str(best), bucket, key)

    uri = "s3://" + bucket + "/" + key
    print("uploaded", uri)

    return uri


# ##############################
# Pipeline step: evaluate
# ##############################
@dsl.component(
    base_image="python:3.12",
    packages_to_install=["ultralytics-opencv-headless", "boto3", "pyyaml"],
)
def evaluate(
    model_uri: str,
    processed_uri: str,
    region: str,
    imgsz: int,
    metrics: Output[Metrics],
) -> float:
    import os
    from pathlib import Path

    import boto3
    import yaml

    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    from ultralytics import YOLO

    s3 = boto3.client("s3", region_name=region)

    # the val split
    bucket, _, prefix = processed_uri.removeprefix("s3://").partition("/")
    root = Path("/tmp/data")
    pages = s3.get_paginator("list_objects_v2")
    for page in pages.paginate(Bucket=bucket, Prefix=prefix + "/"):
        for obj in page.get("Contents", []):
            relative = obj["Key"][len(prefix) + 1:]
            if not relative or relative.endswith("/"):
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(target))

    data_yaml = root / "data.yaml"
    cfg = yaml.safe_load(data_yaml.read_text())
    cfg["path"] = str(root)
    data_yaml.write_text(yaml.safe_dump(cfg, sort_keys=False))

    # the trained weights
    model_bucket, _, model_key = model_uri.removeprefix("s3://").partition("/")
    best = Path("/tmp/best.pt")
    s3.download_file(model_bucket, model_key, str(best))

    # ##############################
    # evaluate
    # ##############################
    result = YOLO(str(best)).val(
        data=str(data_yaml),
        imgsz=imgsz,
        device="cpu",
        plots=False,
        # without an explicit project ultralytics writes to a cwd it cannot use
        project="/tmp/val",
        name="eval",
        exist_ok=True,
    )

    values = {
        "mAP50": float(result.box.map50),
        "mAP50-95": float(result.box.map),
        "precision": float(result.box.mp),
        "recall": float(result.box.mr),
    }
    for name, value in values.items():
        metrics.log_metric(name, value)
        print(name + "=" + str(value))

    return values["mAP50"]


# ##############################
# Pipeline step: register_model
# ##############################
@dsl.component(
    base_image="python:3.12",
    packages_to_install=["ultralytics-opencv-headless", "onnxruntime",
                         "boto3", "pyyaml", "model-registry"],
)
def register_model(
    model_uri: str,
    processed_uri: str,
    map50: float,
    bucket: str,
    region: str,
    prefix: str,
    run_id: str,
    imgsz: int,
    model_name: str,
    verify_images: int,
    max_box_delta_px: float,
) -> str:
    """
    Export best.pt into the artifact layout, verify it, then register.

    A lightweight component cannot import from the repo, so the layout and the
    pre/post-processing are copied from inference/src/.
    """
    import json
    import os
    import shutil
    from pathlib import Path

    import boto3
    import numpy as np
    import yaml

    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    s3 = boto3.client("s3", region_name=region)

    OPSET = 19
    BOX_CHANNELS = 4
    CONF, IOU = 0.25, 0.45

    # ------------------------------------------------------------------
    # copied from inference/src/inference.py
    # ------------------------------------------------------------------
    import cv2

    def preprocess(image_bgr, imgsz):
        """BGR uint8 HWC -> normalized float32 NCHW, plus the geometry to undo it."""
        height, width = image_bgr.shape[:2]
        scale = min(imgsz / height, imgsz / width)
        new_h, new_w = round(height * scale), round(width * scale)

        resized = cv2.resize(image_bgr, (new_w, new_h),
                             interpolation=cv2.INTER_LINEAR)
        pad_x, pad_y = (imgsz - new_w) // 2, (imgsz - new_h) // 2

        # 114 is the ultralytics padding value
        canvas = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        rgb = canvas[:, :, ::-1]
        tensor = rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
        return tensor[np.newaxis, ...], scale, (pad_x, pad_y)

    def nms(boxes, scores, iou_threshold):
        """Greedy non-maximum suppression over corner-form boxes."""
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            best = order[0]
            keep.append(int(best))
            if order.size == 1:
                break

            rest = order[1:]
            inter_x1 = np.maximum(x1[best], x1[rest])
            inter_y1 = np.maximum(y1[best], y1[rest])
            inter_x2 = np.minimum(x2[best], x2[rest])
            inter_y2 = np.minimum(y2[best], y2[rest])
            inter = (np.maximum(0.0, inter_x2 - inter_x1)
                     * np.maximum(0.0, inter_y2 - inter_y1))

            iou = inter / (areas[best] + areas[rest] - inter)
            order = rest[iou <= iou_threshold]

        return keep

    def postprocess(output, scale, pads, original_shape, names,
                    conf_threshold=CONF, iou_threshold=IOU):
        """
        Raw ONNX output -> detections in the original image's coordinates.

        YOLO11 (1, 4+nc, anchors) needs thresholding and NMS; YOLO26
        (1, max_det, 6) is [x1,y1,x2,y2,score,class] and NMS-free, but the
        head emits max_det rows whatever their score, so it still needs the
        confidence filter.
        """
        predictions = output[0]

        if predictions.ndim == 2 and predictions.shape[1] == 6:
            boxes = predictions[:, :BOX_CHANNELS].copy()
            confidences = predictions[:, 4]
            class_ids = predictions[:, 5].astype(int)

            mask = confidences >= conf_threshold
            if not mask.any():
                return []
            boxes, confidences = boxes[mask], confidences[mask]
            class_ids = class_ids[mask]
        else:
            predictions = predictions.T
            boxes_xywh = predictions[:, :BOX_CHANNELS]
            class_scores = predictions[:, BOX_CHANNELS:]

            confidences = class_scores.max(axis=1)
            class_ids = class_scores.argmax(axis=1)

            mask = confidences >= conf_threshold
            if not mask.any():
                return []

            sel = boxes_xywh[mask]
            boxes = np.empty_like(sel)
            half_w, half_h = sel[:, 2] / 2, sel[:, 3] / 2
            boxes[:, 0] = sel[:, 0] - half_w
            boxes[:, 1] = sel[:, 1] - half_h
            boxes[:, 2] = sel[:, 0] + half_w
            boxes[:, 3] = sel[:, 1] + half_h

            confidences, class_ids = confidences[mask], class_ids[mask]

            keep = nms(boxes, confidences, iou_threshold)
            boxes, confidences = boxes[keep], confidences[keep]
            class_ids = class_ids[keep]

        # undo the letterbox: remove padding, then divide out the resize
        pad_x, pad_y = pads
        boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / scale
        boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / scale

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

    # ------------------------------------------------------------------
    # 1. class names, from the dataset that produced the model
    # ------------------------------------------------------------------
    data_bucket, _, data_prefix = processed_uri.removeprefix(
        "s3://").partition("/")
    data_cfg = yaml.safe_load(
        s3.get_object(Bucket=data_bucket,
                      Key=data_prefix + "/data.yaml")["Body"].read()
    )
    names = list(data_cfg["names"])

    # ------------------------------------------------------------------
    # 2. export into the artifact layout: serve/{model.onnx,metadata.json}
    # ------------------------------------------------------------------
    from ultralytics import YOLO

    src_bucket, _, src_key = model_uri.removeprefix("s3://").partition("/")
    best = Path("/tmp/best.pt")
    s3.download_file(src_bucket, src_key, str(best))

    exported = Path(YOLO(str(best)).export(
        format="onnx", imgsz=imgsz, opset=OPSET, simplify=True, dynamic=False))

    out_root = Path("/tmp/serve")
    out_root.mkdir(parents=True, exist_ok=True)

    onnx = out_root / "model.onnx"
    shutil.move(str(exported), onnx)

    # the graph carries neither class names nor imgsz; the predictor needs both
    (out_root / "metadata.json").write_text(json.dumps({
        "imgsz": int(imgsz),
        "names": names,
        "opset": OPSET,
        "run_id": run_id,
        "mAP50": map50,
    }, indent=2))

    print("exported", onnx, "opset", OPSET, "names", names)

    # ------------------------------------------------------------------
    # 3. verify the export against the .pt before anything ships
    # ------------------------------------------------------------------
    import onnxruntime as ort

    # a handful of val images, straight from the split this model trained on
    val_prefix = data_prefix + "/val/images/"
    listing = s3.list_objects_v2(
        Bucket=data_bucket, Prefix=val_prefix, MaxKeys=verify_images)
    keys = [o["Key"] for o in listing.get("Contents", [])
            if not o["Key"].endswith("/")]
    if not keys:
        raise RuntimeError(
            "no val images under " + val_prefix + "; export cannot be verified")

    session = ort.InferenceSession(
        str(onnx), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    reference = YOLO(str(best))

    worst = 0.0
    mismatches = 0
    checked = 0

    for key in keys:
        local = Path("/tmp/verify") / Path(key).name
        local.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(data_bucket, key, str(local))

        image = cv2.imread(str(local))
        if image is None:
            continue
        checked += 1

        # served path: letterbox -> graph -> NMS -> un-letterbox
        tensor, scale, pads = preprocess(image, imgsz)
        output = session.run(None, {input_name: tensor})[0]
        actual = postprocess(output, scale, pads,
                             image.shape[:2], names, CONF, IOU)

        # reference path
        # rect=False: predict() defaults to rectangular inference, padding only
        # to a stride multiple; the export is locked to a square input.
        expected = reference.predict(str(local), imgsz=imgsz, conf=CONF,
                                     iou=IOU, device="cpu", verbose=False,
                                     rect=False)[0]
        exp_boxes = expected.boxes.xyxy.cpu().numpy()

        if len(actual) != len(exp_boxes):
            mismatches += 1
            print("verify", Path(key).name, "COUNT MISMATCH",
                  len(actual), "vs", len(exp_boxes))
            continue

        # both paths return detections ordered by confidence
        delta = 0.0
        for det, box in zip(actual, exp_boxes):
            corners = [det["box"][k] for k in ("x1", "y1", "x2", "y2")]
            delta = max(delta, max(abs(a - b) for a, b in zip(corners, box)))
        worst = max(worst, delta)
        print("verify", Path(key).name, "max_px", round(delta, 2))

    if not checked:
        raise RuntimeError("no val image could be decoded; export unverified")

    print("verify: worst", round(worst, 2), "px over", checked, "images,",
          "tolerance", max_box_delta_px, "| count mismatches", mismatches)

    if mismatches or worst > max_box_delta_px:
        # a coordinate bug is silent at serving time, so fail here instead
        raise RuntimeError(
            "export verification FAILED: " + str(mismatches) +
            " count mismatches, worst box delta " + str(round(worst, 2)) + "px")

    # ------------------------------------------------------------------
    # 4. upload
    # ------------------------------------------------------------------
    base = prefix.rstrip("/") + "/" + run_id

    # serve/ holds only what the predictor mounts: KServe pulls the whole
    # prefix, so the weights and metrics stay outside it.
    serve = base + "/serve"
    for path in sorted(out_root.rglob("*")):
        if path.is_file():
            s3.upload_file(str(path), bucket,
                           serve + "/" + path.relative_to(out_root).as_posix())

    metrics = Path("/tmp/metrics.json")
    metrics.write_text(json.dumps(
        {"mAP50": map50, "run_id": run_id}, indent=2))
    s3.upload_file(str(metrics), bucket, base + "/eval/metrics.json")

    storage_uri = "s3://" + bucket + "/" + serve

    # ------------------------------------------------------------------
    # 5. register
    # ------------------------------------------------------------------
    from model_registry import ModelRegistry

    registry = ModelRegistry(
        server_address="http://model-registry-service.kubeflow-user-example-com.svc.cluster.local",
        port=8080,
        author="kfp",
        is_secure=False,
    )
    registry.register_model(
        model_name,
        storage_uri,
        model_format_name="onnx",
        model_format_version="1",
        version=run_id,
        description="YOLO26n license-plate detector",
        metadata={"mAP50": map50, "imgsz": imgsz, "run_id": run_id,
                  "opset": OPSET, "verified_px": round(worst, 2)},
    )

    print("registered", model_name, run_id, "->", storage_uri)
    return storage_uri


# ##############################
# Create pipeline
# ##############################
@dsl.pipeline
def yolo_pipeline(
    bucket: str = "kubeflow-yolo-dev-099139718958",
    dvc_dir_hash: str = "0e94102a7a6b4424a0f1292c2f221072.dir",
    region: str = "ca-central-1",
    prefix: str = "pipeline/processed",
    runs_prefix: str = "pipeline/runs",
    model_name: str = "kubeflow-yolo-plate",
    val_fraction: float = 0.2,
    split_seed: int = 0,
    epochs: int = 1,
    batch: int = 8,
    imgsz: int = 640,
    weights: str = "yolo26n.pt",
    min_map50: float = 0.5,
    # export gate: images to check, and how far a box may drift from the .pt
    verify_images: int = 8,
    max_box_delta_px: float = 2.0,
):
    # prepare_data step
    prepare = prepare_data(
        bucket=bucket,
        dvc_dir_hash=dvc_dir_hash,
        region=region,
        prefix=prefix,
        val_fraction=val_fraction,
        split_seed=split_seed,
    )

    # train
    trained = (
        train(
            processed_uri=prepare.output,
            region=region,
            prefix=runs_prefix,
            run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
            epochs=epochs,
            batch=batch,
            imgsz=imgsz,
            weights=weights,
            # ultralytics device index, not a boolean
            device="0",
        )
        .set_cpu_request("2")
        .set_cpu_limit("3")
        .set_memory_request("8Gi")
        .set_memory_limit("12Gi")
        .set_accelerator_type("nvidia.com/gpu")
        .set_accelerator_limit(1)
        .set_retry(num_retries=2)
    )

    # train model with gpu node
    kubernetes.add_node_selector(trained, "workload-class", "gpu")
    kubernetes.add_toleration(
        trained, key="workload-class", operator="Equal", value="gpu",
        effect="NoSchedule",
    )

    kubernetes.empty_dir_mount(
        trained,
        volume_name="dshm",
        mount_path="/dev/shm",
        medium="Memory",
        size_limit="2Gi",
    )

    # evaluate
    scored = evaluate(
        model_uri=trained.output,
        processed_uri=prepare.output,
        region=region,
        imgsz=imgsz,
    ).set_memory_limit("4Gi")

    # register model
    register_model(
        model_uri=trained.output,
        processed_uri=prepare.output,
        map50=scored.outputs["Output"],
        bucket=bucket,
        region=region,
        prefix=runs_prefix,
        run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
        imgsz=imgsz,
        model_name=model_name,
        verify_images=verify_images,
        max_box_delta_px=max_box_delta_px,
    ).set_memory_limit("4Gi")
