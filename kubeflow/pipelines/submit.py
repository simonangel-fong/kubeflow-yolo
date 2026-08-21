"""
Submit the pipeline to KFP.

Run from a terminal *inside the Kubeflow notebook*:

    pip install kfp
    python compile.py && python submit.py
    python submit.py --epochs 10 --lr0 0.005     # override hyperparameters

Authentication uses the notebook pod's projected ServiceAccount token. The
notebook needs the kfp-api-token PodDefault applied and the label set, or the
token path does not exist and the API rejects the request -- see
notebook-cpu.yaml and docs/kubeflow.md. Submitting from a laptop does not work:
ml-pipeline-ui is a ClusterIP service behind istio.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import kfp
from kfp.client.set_volume_credentials import ServiceAccountTokenVolumeCredentials

NAMESPACE = "kubeflow-user-example-com"
# The in-cluster service, not the public gateway: the gateway front-ends
# oauth2-proxy, which answers a token-authenticated call with a login page.
HOST = "http://ml-pipeline-ui.kubeflow.svc.cluster.local"
TOKEN_PATH = "/var/run/secrets/kubeflow/pipelines/token"

PACKAGE = Path(__file__).parent / "yolo_pipeline.yaml"
EXPERIMENT = "yolo-plate-detector"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--lr0", type=float, default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--dvc-dir-hash", default=None,
                        help="dataset version to train against, from data/raw.dvc")
    parser.add_argument("--experiment", default=EXPERIMENT)
    parser.add_argument("--wait", action="store_true",
                        help="block until the run finishes")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not PACKAGE.exists():
        raise SystemExit("run `python compile.py` first: " + str(PACKAGE) + " missing")

    if not Path(TOKEN_PATH).exists():
        raise SystemExit(
            "no ServiceAccount token at " + TOKEN_PATH + ".\n"
            "Submit from a terminal inside the notebook, and make sure the "
            "kfp-api-token PodDefault is applied and the notebook carries the "
            "`kfp-api-token: \"true\"` label (see kubeflow/notebook/)."
        )

    client = kfp.Client(
        host=HOST,
        credentials=ServiceAccountTokenVolumeCredentials(path=TOKEN_PATH),
    )

    # Only pass what was overridden; everything else keeps the pipeline default.
    overrides = {
        "epochs": args.epochs,
        "batch": args.batch,
        "lr0": args.lr0,
        "imgsz": args.imgsz,
        "dvc_dir_hash": args.dvc_dir_hash,
    }
    arguments = {k: v for k, v in overrides.items() if v is not None}

    experiment = client.create_experiment(name=args.experiment, namespace=NAMESPACE)
    run = client.run_pipeline(
        experiment_id=experiment.experiment_id,
        job_name="yolo-" + ("-".join(str(v) for v in arguments.values()) or "default"),
        pipeline_package_path=str(PACKAGE),
        arguments=arguments,
    )

    print("run", run.run_id)
    print("arguments", arguments or "(defaults)")

    if args.wait:
        result = client.wait_for_run_completion(run.run_id, timeout=7200)
        print("state", result.state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
