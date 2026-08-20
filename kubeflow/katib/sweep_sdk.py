"""
Katib hyperparameter sweep for the YOLO license-plate model, via the SDK.

Run from a Kubeflow notebook in the profile namespace:

    python sweep_sdk.py

The objective runs as a Python function in the trial pod, so no custom image
is needed: `packages_to_install` builds the environment at pod start.
"""

from kubeflow.optimizer import (
    Objective,
    OptimizerClient,
    RandomSearch,
    Search,
    TrialConfig,
)
from kubeflow.trainer.types.types import CustomTrainer, TrainJobTemplate

BUCKET = "kubeflow-yolo-dev-099139718958"
REGION = "ca-central-1"


def objective(lr0: float, batch: int, epochs: int):
    """One trial: pull the dataset, train, print the metric Katib collects."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    import boto3
    from ultralytics import YOLO

    root = Path("/tmp/yolo")
    raw = root / "raw"
    processed = root / "processed"
    raw.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name="ca-central-1")

    def dvc_key(md5: str) -> str:
        return f"dvcstore/files/md5/{md5[:2]}/{md5[2:]}"

    # data/raw.dvc pins the dataset; its .dir object maps hash -> filename
    head = s3.get_object(
        Bucket="kubeflow-yolo-dev-099139718958",
        Key=dvc_key("0e94102a7a6b4424a0f1292c2f221072.dir"),
    )
    manifest = json.loads(head["Body"].read())

    def fetch(entry):
        target = raw / entry["relpath"]
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(
            "kubeflow-yolo-dev-099139718958", dvc_key(entry["md5"]), str(target)
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(fetch, manifest))

    # 80/20 split, seeded so every trial sees the same data
    import random
    import shutil

    stems = sorted(
        p.stem for p in raw.iterdir()
        if p.suffix.lower() in {".jpeg", ".jpg", ".png"}
    )
    random.Random(0).shuffle(stems)
    cut = int(len(stems) * 0.8)

    for split, names in (("train", stems[:cut]), ("val", stems[cut:])):
        for sub in ("images", "labels"):
            (processed / split / sub).mkdir(parents=True, exist_ok=True)
        for stem in names:
            src_img = next(
                p for p in raw.glob(f"{stem}.*")
                if p.suffix.lower() in {".jpeg", ".jpg", ".png"}
            )
            shutil.copy(src_img, processed / split / "images" / src_img.name)
            label = raw / f"{stem}.txt"
            if label.exists():
                shutil.copy(label, processed / split / "labels" / label.name)

    names = (raw / "classes.txt").read_text().split()
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        f"path: {processed}\ntrain: train/images\nval: val/images\n"
        f"nc: {len(names)}\nnames: {names}\n"
    )

    model = YOLO("yolo11n.pt")
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        batch=batch,
        lr0=lr0,
        imgsz=640,
        device="cpu",
        workers=2,
        project=str(root / "runs"),
        name="trial",
        exist_ok=True,
        plots=False,
    )

    metrics = model.val(data=str(data_yaml), imgsz=640, device="cpu", plots=False)

    # Katib's StdOut collector parses `name=value`, so the spacing matters.
    print(f"mAP50={metrics.box.map50:.6f}")
    print(f"mAP50-95={metrics.box.map:.6f}")


if __name__ == "__main__":
    client = OptimizerClient()

    job_id = client.optimize(
        trial_template=TrainJobTemplate(
            runtime="torch-distributed",
            trainer=CustomTrainer(
                func=objective,
                packages_to_install=[
                    "ultralytics>=8.3.0",
                    "boto3",
                ],
                resources_per_node={"cpu": "2", "memory": "6Gi"},
                env={"YOLO_CONFIG_DIR": "/tmp/ultralytics",
                     "MPLCONFIGDIR": "/tmp/matplotlib",
                     "AWS_REGION": REGION},
            ),
        ),
        search_space={
            "lr0": Search.loguniform(1e-4, 1e-2),
            "batch": Search.choice([4, 8]),
            "epochs": Search.choice([3]),
        },
        objectives=[Objective(metric="mAP50", direction="maximize")],
        algorithm=RandomSearch(),
        trial_config=TrialConfig(num_trials=4, parallel_trials=2, max_failed_trials=2),
    )

    print(f"submitted: {job_id}")
