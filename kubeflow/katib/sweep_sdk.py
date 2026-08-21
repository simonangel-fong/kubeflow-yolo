"""
Katib hyperparameter sweep for the YOLO license-plate model.

Run from a terminal inside the Kubeflow notebook:

    pip install kubeflow-katib
    python sweep_sdk.py
"""

import kubeflow.katib as katib

NAMESPACE = "kubeflow-user-example-com"
BUCKET = "kubeflow-yolo-dev-099139718958"
DVC_DIR_HASH = "0e94102a7a6b4424a0f1292c2f221072.dir"


def objective(parameters):
    """Runs inside the trial pod. Katib passes every parameter as a string."""
    import json
    import random
    import shutil
    import subprocess
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    # packages_to_install runs before this, and ultralytics drags in the GUI
    # build of opencv, overwriting the headless one. The base image has no
    # libxcb, so importing cv2 fails. Swap it back before importing anything.
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "-q",
         "opencv-python", "opencv-contrib-python"],
        check=False,
    )
    # numpy<2 as well: the base image ships torch 2.2.1 built against numpy 1.x,
    # and ultralytics pulls numpy 2.x, which breaks the torch/numpy bridge.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--force-reinstall",
         "opencv-python-headless", "numpy<2"],
        check=True,
    )

    import boto3
    from ultralytics import YOLO

    lr0 = float(parameters["lr0"])
    batch = int(parameters["batch"])
    epochs = int(parameters["epochs"])

    bucket = "kubeflow-yolo-dev-099139718958"
    root = Path("/tmp/yolo")
    raw = root / "raw"
    processed = root / "processed"
    raw.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client("s3", region_name="ca-central-1")

    def dvc_key(md5):
        return "dvcstore/files/md5/" + md5[:2] + "/" + md5[2:]

    # data/raw.dvc pins the dataset; the .dir object maps hash -> filename
    manifest = json.loads(
        s3.get_object(
            Bucket=bucket,
            Key=dvc_key("0e94102a7a6b4424a0f1292c2f221072.dir"),
        )["Body"].read()
    )

    def fetch(entry):
        target = raw / entry["relpath"]
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, dvc_key(entry["md5"]), str(target))

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(fetch, manifest))

    # 80/20 split, seeded so every trial sees the same data
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
            img = next(
                p for p in raw.glob(stem + ".*")
                if p.suffix.lower() in {".jpeg", ".jpg", ".png"}
            )
            shutil.copy(img, processed / split / "images" / img.name)
            label = raw / (stem + ".txt")
            if label.exists():
                shutil.copy(label, processed / split / "labels" / label.name)

    class_names = (raw / "classes.txt").read_text().split()
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        "path: " + str(processed) + "\n"
        "train: train/images\n"
        "val: val/images\n"
        "nc: " + str(len(class_names)) + "\n"
        "names: " + str(class_names) + "\n"
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

    # Katib's StdOut collector parses name=value
    print("mAP50=" + str(metrics.box.map50))
    print("mAP50-95=" + str(metrics.box.map))


if __name__ == "__main__":
    client = katib.KatibClient(namespace=NAMESPACE)

    client.tune(
        name="yolo-sweep",
        objective=objective,
        # The admission webhook rejects a null feasibleSpace.distribution, which
        # is what katib.search.* emits by default, so build the specs directly.
        parameters={
            "lr0": katib.V1beta1ParameterSpec(
                name="lr0",
                parameter_type="double",
                feasible_space=katib.V1beta1FeasibleSpace(
                    min="0.001", max="0.05", distribution="uniform"
                ),
            ),
            "batch": katib.V1beta1ParameterSpec(
                name="batch",
                parameter_type="categorical",
                feasible_space=katib.V1beta1FeasibleSpace(list=["4", "8"]),
            ),
            "epochs": katib.V1beta1ParameterSpec(
                name="epochs",
                parameter_type="categorical",
                feasible_space=katib.V1beta1FeasibleSpace(list=["3"]),
            ),
        },
        objective_metric_name="mAP50",
        additional_metric_names=["mAP50-95"],
        objective_type="maximize",
        algorithm_name="random",
        max_trial_count=4,
        parallel_trial_count=2,
        max_failed_trial_count=2,
        # opencv-python-headless first: ultralytics pulls the GUI build, which
        # needs libxcb and is not present in the base image.
        packages_to_install=["opencv-python-headless", "ultralytics", "boto3"],
        resources_per_trial={"cpu": "2", "memory": "6Gi"},
        env_per_trial={
            "YOLO_CONFIG_DIR": "/tmp/ultralytics",
            "MPLCONFIGDIR": "/tmp/matplotlib",
            "AWS_REGION": "ca-central-1",
        },
        retain_trials=True,
    )

    print("submitted")
