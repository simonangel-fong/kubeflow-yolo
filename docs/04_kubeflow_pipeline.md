# Kubeflow: Pipeline

[Back](../README.md)

- [Kubeflow: Pipeline](#kubeflow-pipeline)
  - [Pipeline Design](#pipeline-design)
    - [Output layout](#output-layout)
  - [Pipeline](#pipeline)

---

## Pipeline Design

```txt
prepare_data -> train -> evaluate -> register_model
```

| Step             | Does                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------- |
| `prepare_data`   | Reads the DVC-tracked dataset from S3, splits train/val server-side, writes `data.yaml` |
| `train`          | Fine-tunes `yolo26n.pt` on a GPU node, uploads `best.pt`                                |
| `evaluate`       | Re-validates `best.pt`, logs mAP to the run's Metrics tab                               |
| `register_model` | Exports ONNX, uploads the bundle, registers in Model Registry                           |

---

### Output layout

```txt
s3://<bucket>/pipeline/runs/<run-id>/
├── train/best.pt                       # trained weights
├── eval/metrics.json                   # mAP50 and the run id
└── serve/                              # registered storage_uri
    ├── model.onnx
    └── metadata.json                   # imgsz, names, opset, run_id, mAP50
```

`serve/` is what the predictor mounts, and holds nothing else: KServe pulls
the whole prefix, so the weights and metrics stay outside it. `metadata.json`
carries the class names and `imgsz` the graph does not.

The model registers as `kubeflow-yolo-plate`, version `<run-id>`, with the
export verified against `best.pt` before it is registered.

---

## Pipeline

```sh
pip install kfp

cd ~/kubeflow-yolo/kubeflow/pipelines
python compile.py
# compiled /home/jovyan/kubeflow-yolo/kubeflow/pipelines/yolo_pipeline.yaml

python submit.py
# run 3f9c1a72-...
# arguments (defaults)

# override hyperparameters
python submit.py --epochs 10 --lr0 0.005

# confirm
kubectl get workflows -n kubeflow-user-example-com --sort-by=.metadata.creationTimestamp
kubectl logs -n kubeflow-user-example-com <pod> -c main
```
