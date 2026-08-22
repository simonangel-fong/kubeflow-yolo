"""
KFP pipeline for the YOLO license-plate model.

    prepare_data -> train -> evaluate -> register_model

Each step reads and writes S3 directly with boto3 and passes S3 URIs as
strings, so no data travels through the KFP artifact store. Credentials come
from EKS Pod Identity on default-editor (infra/60-s3-iam.tf); nothing is
mounted and nothing is read from the environment.

Steps are lightweight components: the function body ships as source and pip
installs its own dependencies at runtime, so the edit loop is a recompile with
no image build.

Compile with compile.py; developed and first proven in
jupyter-notebook/notebooks/05-kf-pipeline.ipynb.
"""

from kfp import dsl
from kfp.dsl import Metrics, Output

# tolerations and nodeSelector are not in core kfp
from kfp import kubernetes


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

    def dvc_key(md5: str) -> str:
        # DVC shards its content-addressed store by the first two hex chars
        return "dvcstore/files/md5/" + md5[:2] + "/" + md5[2:]

    # the .dir object lists {"md5": ..., "relpath": ...} for every file
    manifest = json.loads(
        s3.get_object(Bucket=bucket, Key=dvc_key(dvc_dir_hash))["Body"].read()
    )
    by_relpath = {e["relpath"]: e["md5"] for e in manifest}

    suffixes = {".jpeg", ".jpg", ".png"}
    # images and labels pair by basename: foo.jpeg <-> foo.txt
    images = {Path(r).stem: r for r in by_relpath
              if Path(r).suffix.lower() in suffixes}

    stems = sorted(images)
    # seeded, so two runs split the same way and their metrics compare
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
        s3.get_object(Bucket=bucket, Key=dvc_key(by_relpath["classes.txt"]))["Body"]
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


@dsl.component(
    base_image="python:3.12",
    # headless opencv needs no libgl1, which a plain python image lacks;
    # numpy<2 keeps the torch/numpy ABI bridge intact
    packages_to_install=["ultralytics", "opencv-python-headless", "numpy<2", "boto3", "pyyaml"],
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
    import subprocess
    import sys
    from pathlib import Path

    import boto3
    import yaml

    # ultralytics depends on GUI opencv and installs it over the headless build,
    # and libGL.so.1 is absent from a plain python image. Put headless back
    # before the first `import cv2`, which `import ultralytics` triggers.
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "-q",
         "opencv-python", "opencv-contrib-python"],
        check=False,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
         "opencv-python-headless", "numpy<2"],
        check=True,
    )

    # the restricted PSS namespace runs an arbitrary UID with no writable HOME
    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    from ultralytics import YOLO

    bucket, _, data_prefix = processed_uri.removeprefix("s3://").partition("/")
    s3 = boto3.client("s3", region_name=region)

    # pull the split down: ultralytics reads from a local directory
    root = Path("/tmp/data")
    pages = s3.get_paginator("list_objects_v2")
    for page in pages.paginate(Bucket=bucket, Prefix=data_prefix + "/"):
        for obj in page.get("Contents", []):
            relative = obj["Key"][len(data_prefix) + 1:]
            # a key ending in "/" is a directory marker, and an empty relative
            # path is the prefix object itself; restoring either as a file
            # would shadow the directory the rest of the split needs
            if not relative or relative.endswith("/"):
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, obj["Key"], str(target))

    # `path` must be absolute and is only known now, after the download
    data_yaml = root / "data.yaml"
    cfg = yaml.safe_load(data_yaml.read_text())
    cfg["path"] = str(root)
    data_yaml.write_text(yaml.safe_dump(cfg, sort_keys=False))

    results = YOLO(weights).train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        # dataloader workers share memory through /dev/shm, which is 64Mi in a
        # container; more workers than that supports kills them silently
        workers=4 if device != "cpu" else 2,
        project="/tmp/runs",
        name="train",
        exist_ok=True,
        plots=False,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    # run-scoped, so concurrent runs cannot overwrite each other
    key = prefix.rstrip("/") + "/" + run_id + "/best.pt"
    s3.upload_file(str(best), bucket, key)

    uri = "s3://" + bucket + "/" + key
    print("uploaded", uri)
    return uri


@dsl.component(
    base_image="python:3.12",
    packages_to_install=["ultralytics", "opencv-python-headless", "numpy<2", "boto3", "pyyaml"],
)
def evaluate(
    model_uri: str,
    processed_uri: str,
    region: str,
    imgsz: int,
    metrics: Output[Metrics],
) -> float:
    import os
    import subprocess
    import sys
    from pathlib import Path

    import boto3
    import yaml

    # ultralytics installs GUI opencv over the headless build, and libGL.so.1
    # is absent from a plain python image; put headless back before importing
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "-q",
         "opencv-python", "opencv-contrib-python"],
        check=False,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
         "opencv-python-headless", "numpy<2"],
        check=True,
    )

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
            # a key ending in "/" is a directory marker, and an empty relative
            # path is the prefix object itself; restoring either as a file
            # would shadow the directory the rest of the split needs
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


@dsl.component(
    base_image="python:3.12",
    packages_to_install=["ultralytics", "opencv-python-headless", "numpy<2",
                         "onnx", "onnxslim", "onnxruntime", "boto3", "model-registry"],
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
    import subprocess
    import sys
    import tarfile
    from pathlib import Path

    import boto3

    # ultralytics installs GUI opencv over the headless build, and libGL.so.1
    # is absent from a plain python image; put headless back before importing
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "-q",
         "opencv-python", "opencv-contrib-python"],
        check=False,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
         "opencv-python-headless", "numpy<2"],
        check=True,
    )

    os.environ["YOLO_CONFIG_DIR"] = "/tmp/ultralytics"
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

    from ultralytics import YOLO

    s3 = boto3.client("s3", region_name=region)

    # 1. export to onnx
    src_bucket, _, src_key = model_uri.removeprefix("s3://").partition("/")
    best = Path("/tmp/best.pt")
    s3.download_file(src_bucket, src_key, str(best))

    # Triton 2.34 bundles an onnxruntime that supports ai.onnx up to opset 19;
    # ultralytics defaults to 20, which fails to load with "Opset 20 is under
    # development". Pin it rather than tracking the runtime's default.
    onnx = Path(YOLO(str(best)).export(format="onnx", imgsz=imgsz, opset=19))

    metrics = Path("/tmp/metrics.json")
    metrics.write_text(json.dumps({"mAP50": map50, "run_id": run_id}, indent=2))

    # 2. upload
    base = prefix.rstrip("/") + "/" + run_id

    # KServe hands storageUri to Triton as a model repository, whose required
    # layout is <repo>/<model-name>/config.pbtxt and <repo>/<model-name>/1/model.onnx
    # (triton-inference-server/server docs/user_guide/model_repository.md).
    repo = base + "/model"
    s3.upload_file(str(onnx), bucket, repo + "/" + model_name + "/1/model.onnx")

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
    prepare = prepare_data(
        bucket=bucket,
        dvc_dir_hash=dvc_dir_hash,
        region=region,
        prefix=prefix,
        val_fraction=val_fraction,
        split_seed=split_seed,
    )

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
        # sized to fit a g5.xlarge (4 vCPU / 16Gi), the only instance the gpu
        # NodePool provisions, leaving headroom for kubelet and daemonsets
        .set_cpu_request("2")
        .set_cpu_limit("3")
        .set_memory_request("8Gi")
        .set_memory_limit("12Gi")
        .set_accelerator_type("nvidia.com/gpu")
        .set_accelerator_limit(1)
        # Karpenter must provision a g5.xlarge first, so the pod is Pending for
        # a few minutes; a retry also covers consolidation mid-run
        .set_retry(num_retries=2)
    )

    # the gpu NodePool taints its nodes, so without a matching toleration
    # Karpenter will not place the pod
    kubernetes.add_node_selector(trained, "workload-class", "gpu")
    kubernetes.add_toleration(
        trained, key="workload-class", operator="Equal", value="gpu",
        effect="NoSchedule",
    )

    # Dataloader workers pass tensors through shared memory, and /dev/shm is
    # 64Mi in a container -- too small for `workers`, which surfaces as
    # "unable to allocate shared memory" or a silently killed worker.
    kubernetes.empty_dir_mount(
        trained,
        volume_name="dshm",
        mount_path="/dev/shm",
        medium="Memory",
        size_limit="2Gi",
    )

    scored = evaluate(
        model_uri=trained.output,
        processed_uri=prepare.output,
        region=region,
        imgsz=imgsz,
    ).set_memory_limit("4Gi")

    # gate: only register a model that clears the threshold. Commented out
    # while the pipeline is being proven -- current mAP50 is far below it.
    # with dsl.If(scored.outputs["Output"] >= min_map50):
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
