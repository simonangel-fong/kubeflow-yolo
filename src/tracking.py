"""MLflow helpers for YOLO training.

Ultralytics ships an mlflow callback that logs `trainer.args`, per-epoch
metrics and the contents of `save_dir` (weights, curves, results.csv). It is
enabled by default and reads MLFLOW_TRACKING_URI from the environment, so
training is already tracked without any code here.

What the callback does not record is *what it trained on*. Stage 1 produced
mAP50 of 0.958 and 0.896 from the same config -- the difference was 445 vs 160
training images, which is invisible in the logged params. These helpers add
that provenance so runs stay comparable.
"""

from __future__ import annotations

import os
from pathlib import Path

import mlflow


def dataset_params(processed_dir: Path, raw_dir: Path | None = None) -> dict[str, object]:
    """Facts about the split that `trainer.args` does not capture.

    Without these, two runs with identical hyperparameters but different
    dataset sizes are indistinguishable in the mlflow UI.
    """
    params: dict[str, object] = {}
    for split in ("train", "val"):
        images = list((processed_dir / split / "images").iterdir())
        labels = list((processed_dir / split / "labels").iterdir())
        boxes = sum(
            len([ln for ln in p.read_text().splitlines() if ln.strip()]) for p in labels
        )
        params[f"data.{split}_images"] = len(images)
        params[f"data.{split}_boxes"] = boxes

    total_images = params["data.train_images"] + params["data.val_images"]
    params["data.total_images"] = total_images
    if raw_dir is not None:
        # How much of the available data this run actually used.
        available = len([p for p in raw_dir.iterdir() if p.suffix.lower() != ".txt"])
        params["data.available_images"] = available
        params["data.fraction_used"] = round(total_images / available, 3) if available else 0

    return params


def log_dataset_context(processed_dir: Path, raw_dir: Path | None = None, **extra) -> dict:
    """Attach dataset provenance to the active run.

    Call after `model.train()` -- the ultralytics callback opens the run and
    closes it at train end, so this reopens the same run by id to append.
    """
    params = dataset_params(processed_dir, raw_dir)
    params.update(extra)
    mlflow.log_params(params)
    return params


def latest_run_id(experiment_name: str) -> str | None:
    """Most recent run in an experiment, so a finished run can be reopened."""
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return None
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    return None if runs.empty else runs.iloc[0]["run_id"]


def compare_runs(experiment_name: str, metrics: list[str] | None = None):
    """Runs in one experiment as a table, newest first.

    This is the point of the stage: four stage-1 runs exist and cannot be
    compared because nothing recorded them.
    """
    # The ultralytics callback strips parentheses before logging, so the keys
    # are "metrics/mAP50B", not the "metrics/mAP50(B)" that results.csv uses.
    metrics = metrics or [
        "metrics/mAP50B",
        "metrics/mAP50-95B",
        "metrics/precisionB",
        "metrics/recallB",
    ]
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"no experiment named {experiment_name!r}")

    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
    )
    if runs.empty:
        return runs

    columns = ["tags.mlflow.runName", "params.epochs", "params.imgsz", "params.data.train_images"]
    columns += [f"metrics.{m}" for m in metrics]
    present = [c for c in columns if c in runs.columns]
    table = runs[present].copy()
    table.columns = [c.split(".", 1)[-1] for c in present]
    return table


def tracking_uri() -> str:
    """Resolved tracking URI, for printing in a notebook."""
    return os.environ.get("MLFLOW_TRACKING_URI") or mlflow.get_tracking_uri()
