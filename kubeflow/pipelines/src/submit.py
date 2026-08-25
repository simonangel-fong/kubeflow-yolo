"""
Submit the pipeline to KFP:
    python compile.py && python submit.py
    python submit.py --epochs 50 --batch 16     # override hyperparameters
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import kfp

NAMESPACE = "kubeflow-yolo"
PACKAGE = Path(__file__).parent / "yolo_pipeline.yaml"
EXPERIMENT = "kubeflow-yolo-plate"
PIPELINE = "kubeflow-yolo-plate"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--split-seed", type=int, default=None)
    parser.add_argument("--dvc-dir-hash", default=None,
                        help="dataset version to train against, from data/raw.dvc")
    parser.add_argument("--experiment", default=EXPERIMENT)
    parser.add_argument("--no-cache", action="store_true",
                        help="re-execute every step; needed after the S3 output "
                             "of a cached step has been deleted")
    parser.add_argument("--wait", action="store_true",
                        help="block until the run finishes")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not PACKAGE.exists():
        raise SystemExit(f"run `python compile.py` first: {PACKAGE} missing")

    client = kfp.Client()

    # Only pass what was overridden; everything else keeps the pipeline default.
    overrides = {
        "epochs": args.epochs,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "split_seed": args.split_seed,
        "dvc_dir_hash": args.dvc_dir_hash,
    }
    arguments = {k: v for k, v in overrides.items() if v is not None}

    version_name = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    existing = client.list_pipelines(
        namespace=NAMESPACE, page_size=100).pipelines or []
    pipeline_id = next(
        (p.pipeline_id for p in existing if p.display_name == PIPELINE), None
    )

    if pipeline_id is None:
        pipeline = client.upload_pipeline(
            pipeline_package_path=str(PACKAGE),
            pipeline_name=PIPELINE,
            description="Fetch the dataset from S3, split, train YOLO, evaluate, register.",
            namespace=NAMESPACE,
        )
        pipeline_id = pipeline.pipeline_id
        # the upload creates a default version but does not return its id
        version_id = client.list_pipeline_versions(
            pipeline_id=pipeline_id, page_size=1, sort_by="created_at desc",
        ).pipeline_versions[0].pipeline_version_id
        print("created pipeline", PIPELINE, pipeline_id)
    else:
        version = client.upload_pipeline_version(
            pipeline_package_path=str(PACKAGE),
            pipeline_version_name=version_name,
            pipeline_id=pipeline_id,
        )
        version_id = version.pipeline_version_id
        print("added version", version_name, "to", PIPELINE)

    experiment = client.create_experiment(
        name=args.experiment, namespace=NAMESPACE)
    run = client.run_pipeline(
        experiment_id=experiment.experiment_id,
        job_name="yolo-" + ("-".join(str(v)
                            for v in arguments.values()) or "default"),
        pipeline_id=pipeline_id,
        version_id=version_id,
        params=arguments,
        enable_caching=not args.no_cache,
    )

    print("run", run.run_id)
    print("arguments", arguments or "(defaults)")

    if args.wait:
        # a GPU run waits on Karpenter provisioning a g5.xlarge first
        result = client.wait_for_run_completion(run.run_id, timeout=7200)
        print("state", result.state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
