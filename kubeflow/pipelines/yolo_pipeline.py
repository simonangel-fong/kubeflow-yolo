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
    key = prefix.rstrip("/") + "/" + run_id + "/best.pt"
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
    packages_to_install=["ultralytics-opencv-headless", "onnx", "onnxslim",
                         "boto3", "model-registry"],
)
def register_model(
    model_uri: str,
    map50: float,
    bucket: str,
    region: str,
    prefix: str,
    run_id: str,
    imgsz: int,
    model_name: str,
) -> str:
    import json
    import os
    import tarfile
    from pathlib import Path

    import boto3

    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    from ultralytics import YOLO

    s3 = boto3.client("s3", region_name=region)

    # 1. export to onnx
    src_bucket, _, src_key = model_uri.removeprefix("s3://").partition("/")
    best = Path("/tmp/best.pt")
    s3.download_file(src_bucket, src_key, str(best))

    # Triton 23.05 ships onnxruntime 1.15, which implements opset 19.
    onnx = Path(YOLO(str(best)).export(format="onnx", imgsz=imgsz, opset=19))

    metrics = Path("/tmp/metrics.json")
    metrics.write_text(json.dumps(
        {"mAP50": map50, "run_id": run_id}, indent=2))

    # 2. upload
    base = prefix.rstrip("/") + "/" + run_id

    repo = base + "/model"
    s3.upload_file(str(onnx), bucket, repo + "/" +
                   model_name + "/1/model.onnx")

    # describe the graph from the graph itself rather than hardcoding shapes
    import onnx as onnx_mod

    graph = onnx_mod.load(str(onnx), load_external_data=False).graph
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

    config = nl.join([
        'name: "' + model_name + '"',
        'platform: "onnxruntime_onnx"',
        # the exported graph has a fixed batch dimension, so batching is off
        "max_batch_size: 0",
        "input [",
        ("," + nl).join(spec(v) for v in graph.input),
        "]",
        "output [",
        ("," + nl).join(spec(v) for v in graph.output),
        "]",
        "",
    ])
    s3.put_object(
        Bucket=bucket,
        Key=repo + "/" + model_name + "/config.pbtxt",
        Body=config.encode(),
    )

    # the tarball is an archive, not the servable path
    bundle = Path("/tmp/model.tar.gz")
    with tarfile.open(bundle, "w:gz") as tar:
        for item in (best, onnx, metrics):
            tar.add(item, arcname=item.name)
    s3.upload_file(str(bundle), bucket, base + "/model.tar.gz")
    s3.upload_file(str(metrics), bucket, base + "/metrics.json")

    storage_uri = "s3://" + bucket + "/" + repo

    # 3. register
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
        description="YOLO11n license-plate detector",
        metadata={"mAP50": map50, "imgsz": imgsz, "run_id": run_id},
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
    model_prefix: str = "pipeline/models",
    model_name: str = "yolo-plate-detector",
    val_fraction: float = 0.2,
    split_seed: int = 0,
    epochs: int = 1,
    batch: int = 8,
    imgsz: int = 640,
    weights: str = "yolo11n.pt",
    min_map50: float = 0.5,
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
            prefix=model_prefix,
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
        map50=scored.outputs["Output"],
        bucket=bucket,
        region=region,
        prefix=model_prefix,
        run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
        imgsz=imgsz,
        model_name=model_name,
    )
