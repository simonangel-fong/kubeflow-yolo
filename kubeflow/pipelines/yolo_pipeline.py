"""
KFP pipeline for the YOLO license-plate model.

    fetch_data -> prepare_data -> train -> evaluate

Each step is a lightweight component: the function body ships as source and pip
installs its own dependencies at runtime. That mirrors the Katib objective in
../katib/sweep_sdk.py and keeps the edit loop to a recompile, with no image
build or registry push.

Compile and submit with submit.py; see docs/kubeflow.md for the run notes.
"""

from kfp import dsl
from kfp.dsl import Dataset, Input, Metrics, Model, Output

# Pinned so the runtime does not move when the SDK changes its default.
BASE_IMAGE = "python:3.12"

# numpy<2 keeps the torch/numpy ABI bridge intact. Ultralytics overrides both
# this and the headless opencv on install; _repair_env puts them back.
YOLO_PACKAGES = ["opencv-python-headless", "ultralytics", "boto3", "numpy<2"]

IMAGE_SUFFIXES = (".jpeg", ".jpg", ".png")


def _repair_env():
    """
    Restore headless opencv and numpy<2 after ultralytics overrides them.

    Call before importing ultralytics or cv2. Must be passed through
    `additional_funcs` to exist inside the pod.
    """
    import subprocess
    import sys

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


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["boto3"])
def fetch_data(
    bucket: str,
    dvc_dir_hash: str,
    region: str,
    raw: Output[Dataset],
):
    """
    Pull the DVC-tracked raw dataset out of S3.

    `dvc_dir_hash` is the md5 of the .dir object that `dvc add data/raw` wrote
    into data/raw.dvc. That object is a JSON manifest mapping each file's md5
    to its relative path, so the whole dataset is addressable from one hash --
    which is what makes a pipeline run reproducible against a dataset version.

    Credentials come from EKS Pod Identity via the default-editor service
    account; see infra/61-s3-notebook.tf. Nothing is mounted and nothing is
    read from the environment.
    """
    import json
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    import boto3

    s3 = boto3.client("s3", region_name=region)

    def dvc_key(md5: str) -> str:
        # DVC shards the content-addressed store by the first two hex chars.
        return "dvcstore/files/md5/" + md5[:2] + "/" + md5[2:]

    manifest = json.loads(
        s3.get_object(Bucket=bucket, Key=dvc_key(dvc_dir_hash))["Body"].read()
    )

    root = Path(raw.path)
    root.mkdir(parents=True, exist_ok=True)

    def fetch(entry):
        target = root / entry["relpath"]
        target.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, dvc_key(entry["md5"]), str(target))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(fetch, manifest))

    raw.metadata["files"] = len(manifest)
    raw.metadata["dvc_dir_hash"] = dvc_dir_hash
    print("fetched", len(manifest), "files to", root)


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["pyyaml"])
def prepare_data(
    raw: Input[Dataset],
    val_fraction: float,
    split_seed: int,
    processed: Output[Dataset],
):
    """
    Build the train/val split and the ultralytics dataset descriptor.

    The split is seeded so a rerun with the same seed sees the same images --
    without that, comparing two runs' mAP tells you nothing about the change
    you made.

    data.yaml `path` must be absolute: ultralytics resolves a relative root
    against the process cwd and then its own DATASETS_DIR, never against the
    yaml's own location.
    """
    import random
    import shutil
    from pathlib import Path

    import yaml

    suffixes = {".jpeg", ".jpg", ".png"}
    src = Path(raw.path)
    dst = Path(processed.path)

    stems = sorted(p.stem for p in src.iterdir() if p.suffix.lower() in suffixes)
    random.Random(split_seed).shuffle(stems)
    cut = int(len(stems) * (1 - val_fraction))

    counts = {}
    for split, names in (("train", stems[:cut]), ("val", stems[cut:])):
        for sub in ("images", "labels"):
            (dst / split / sub).mkdir(parents=True, exist_ok=True)
        for stem in names:
            image = next(
                p for p in src.glob(stem + ".*") if p.suffix.lower() in suffixes
            )
            shutil.copy(image, dst / split / "images" / image.name)
            label = src / (stem + ".txt")
            # An image with no label file is a legitimate negative sample.
            if label.exists():
                shutil.copy(label, dst / split / "labels" / label.name)
        counts[split] = len(names)

    class_names = (src / "classes.txt").read_text().split()
    (dst / "data.yaml").write_text(
        yaml.safe_dump(
            {
                "path": str(dst),
                "train": "train/images",
                "val": "val/images",
                "nc": len(class_names),
                "names": class_names,
            },
            sort_keys=False,
        )
    )

    processed.metadata.update(counts)
    processed.metadata["classes"] = class_names
    print("split", counts, "classes", class_names)


@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=YOLO_PACKAGES,
    additional_funcs=[_repair_env],
)
def train(
    processed: Input[Dataset],
    lr0: float,
    batch: int,
    epochs: int,
    imgsz: int,
    weights: str,
    model: Output[Model],
):
    """
    Train YOLO and emit best.pt as the step's Model artifact.

    Ultralytics names save_dir unpredictably when runs collide, so best.pt is
    copied to a fixed path that the evaluate step can rely on.
    """
    import shutil
    from pathlib import Path

    _repair_env()

    from ultralytics import YOLO

    data_yaml = Path(processed.path) / "data.yaml"
    out = Path(model.path)
    out.mkdir(parents=True, exist_ok=True)

    yolo = YOLO(weights)
    results = yolo.train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch,
        lr0=lr0,
        imgsz=imgsz,
        device="cpu",
        workers=2,
        project=str(out / "runs"),
        name="train",
        exist_ok=True,
        plots=False,
    )

    save_dir = Path(results.save_dir)
    shutil.copy2(save_dir / "weights" / "best.pt", out / "best.pt")

    results_csv = save_dir / "results.csv"
    if results_csv.exists():
        shutil.copy2(results_csv, out / "results.csv")

    model.metadata.update(
        {"lr0": lr0, "batch": batch, "epochs": epochs, "imgsz": imgsz,
         "weights": weights, "framework": "ultralytics"}
    )
    print("best.pt written to", out / "best.pt")


@dsl.component(
    base_image=BASE_IMAGE,
    packages_to_install=YOLO_PACKAGES,
    additional_funcs=[_repair_env],
)
def evaluate(
    model: Input[Model],
    processed: Input[Dataset],
    imgsz: int,
    metrics: Output[Metrics],
) -> float:
    """
    Re-validate best.pt and log metrics to the run UI.

    Returns mAP50 so a downstream step -- a registry push gated on quality --
    can branch on it. The printed name=value lines match the format the Katib
    StdOut collector parses, so trial logs and pipeline logs read alike.
    """
    from pathlib import Path

    _repair_env()

    from ultralytics import YOLO

    data_yaml = Path(processed.path) / "data.yaml"
    best = YOLO(str(Path(model.path) / "best.pt"))

    # Without an explicit project ultralytics writes to ./runs/detect, relative
    # to a working directory the pod cannot write to.
    result = best.val(
        data=str(data_yaml),
        imgsz=imgsz,
        device="cpu",
        plots=False,
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


@dsl.component(base_image=BASE_IMAGE, packages_to_install=["boto3"])
def upload_model(
    model: Input[Model],
    bucket: str,
    region: str,
    prefix: str,
    map50: float,
    run_id: str,
    uri: Output[Dataset],
):
    """
    Copy the trained weights to S3 under the KFP run id.

    Keyed by run id so runs never overwrite each other, and accompanied by a
    metrics.json so a later KServe deployment can tell what it is picking up.

    `run_id` arrives as a parameter rather than being read in the body: KFP
    substitutes placeholders like {{$.pipeline_job_uuid}} in the container args
    only, so one embedded in this source would upload to a literal path.
    """
    import json
    from pathlib import Path

    import boto3

    key = prefix.rstrip("/") + "/" + run_id + "/best.pt"

    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(str(Path(model.path) / "best.pt"), bucket, key)
    s3.put_object(
        Bucket=bucket,
        Key=prefix.rstrip("/") + "/" + run_id + "/metrics.json",
        Body=json.dumps({"mAP50": map50, "run_id": run_id}, indent=2).encode(),
    )

    destination = "s3://" + bucket + "/" + key
    Path(uri.path).write_text(destination)
    uri.metadata["uri"] = destination
    print("uploaded", destination)


@dsl.pipeline(
    name="yolo-plate-detector",
    description="Fetch DVC data from S3, split, train YOLO, evaluate, upload.",
)
def yolo_pipeline(
    bucket: str = "kubeflow-yolo-dev-099139718958",
    dvc_dir_hash: str = "0e94102a7a6b4424a0f1292c2f221072.dir",
    region: str = "ca-central-1",
    val_fraction: float = 0.2,
    split_seed: int = 0,
    lr0: float = 0.01,
    batch: int = 8,
    epochs: int = 3,
    imgsz: int = 640,
    weights: str = "yolo11n.pt",
    upload_prefix: str = "models",
):
    fetch = fetch_data(
        bucket=bucket, dvc_dir_hash=dvc_dir_hash, region=region
    ).set_caching_options(True)

    prepare = prepare_data(
        raw=fetch.outputs["raw"],
        val_fraction=val_fraction,
        split_seed=split_seed,
    )

    trained = (
        train(
            processed=prepare.outputs["processed"],
            lr0=lr0,
            batch=batch,
            epochs=epochs,
            imgsz=imgsz,
            weights=weights,
        )
        .set_cpu_request("2")
        .set_cpu_limit("4")
        .set_memory_request("6Gi")
        .set_memory_limit("8Gi")
        # Karpenter can still consolidate a node out from under a long train
        # step; a retry costs less than losing the run.
        .set_retry(num_retries=1)
    )

    scored = evaluate(
        model=trained.outputs["model"],
        processed=prepare.outputs["processed"],
        imgsz=imgsz,
    ).set_memory_limit("4Gi")

    upload_model(
        model=trained.outputs["model"],
        bucket=bucket,
        region=region,
        prefix=upload_prefix,
        map50=scored.outputs["Output"],
        run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
    )
