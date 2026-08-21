# Pipeline

```txt
prepare_data -> train -> evaluate -> register_model
```

| Step | Does |
|------|------|
| `prepare_data` | Reads the DVC-tracked dataset from S3, splits train/val server-side, writes `data.yaml` |
| `train` | Fine-tunes `yolo11n.pt` on a GPU node, uploads `best.pt` |
| `evaluate` | Re-validates `best.pt`, logs mAP to the run's Metrics tab |
| `register_model` | Exports ONNX, uploads the bundle, registers in Model Registry |

Steps pass S3 URIs as strings rather than KFP artifacts, so no data travels
through the artifact store.

## Run

From a terminal **inside the notebook** — `ml-pipeline-ui` is a ClusterIP
service, so this does not work from a laptop.

```sh
pip install kfp kfp-kubernetes

cd ~/kubeflow-yolo/kubeflow/pipelines
python compile.py
python submit.py

# override hyperparameters, or train against a different dataset version
python submit.py --epochs 50 --batch 16
python submit.py --dvc-dir-hash <md5-from-data/raw.dvc>
```

Watch it:

```sh
kubectl get workflows -n kubeflow-user-example-com
kubectl logs -n kubeflow-user-example-com <pod> -c main
```

## Output

Everything for a run lands under one prefix, keyed by run id so runs never
overwrite each other:

```txt
s3://<bucket>/pipeline/models/<run-id>/
├── best.pt
├── metrics.json
├── model.tar.gz          # archive
└── model/model.onnx      # KServe storageUri
```

The model registers as `yolo-plate-detector`, version `<run-id>`.

## Notes

- **GPU.** `train` requests `nvidia.com/gpu: 1` and is sized for a `g5.xlarge`,
  the only instance the `gpu` NodePool provisions. That NodePool taints its
  nodes, so the task carries a matching toleration — without it the pod stays
  Pending and Karpenter never provisions. Expect a few minutes of Pending while
  the node comes up.
- **`dvc_dir_hash` is a parameter, not a constant.** It is the md5 of the
  `.dir` manifest in `data/raw.dvc`, so a run is pinned to a dataset version —
  training against new data is a parameter change, not a code change.
- **Caching.** Steps are cached on their inputs, so re-running with the same
  arguments skips straight to the first thing that changed.
- **The quality gate is commented out** in `yolo_pipeline.py`. Uncomment the
  `dsl.If` around `register_model` once the model clears `min_map50`, or every
  run registers regardless of how it scored.
- **opencv.** `ultralytics` installs GUI opencv over the headless build, and
  `libGL.so.1` is absent from a plain python image, so the steps that import
  ultralytics reinstall headless first.
