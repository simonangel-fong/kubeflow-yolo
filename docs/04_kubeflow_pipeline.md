# Kubeflow: Pipeline

[Back](../README.md)

---

## Pipeline Design

```txt
prepare_data -> train -> evaluate -> register_model
```

| Step             | Does                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------- |
| `prepare_data`   | Reads the DVC-tracked dataset from S3, splits train/val server-side, writes `data.yaml` |
| `train`          | Fine-tunes `yolo11n.pt` on a GPU node, uploads `best.pt`                                |
| `evaluate`       | Re-validates `best.pt`, logs mAP to the run's Metrics tab                               |
| `register_model` | Exports ONNX, uploads the bundle, registers in Model Registry                           |

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
