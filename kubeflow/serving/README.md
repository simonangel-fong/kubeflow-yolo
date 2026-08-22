# Serving

Serves the model the pipeline registered, using KServe.

`modelFormat: onnx` auto-selects `kserve-tritonserver` — the only runtime in
this cluster registered for onnx (`kubectl get clusterservingruntimes`).

## Deploy

Point `storageUri` at the run you want, then apply:

```sh
kubectl apply -f inferenceservice.yaml
kubectl get inferenceservice -n kubeflow-user-example-com -w
```

The URI is a Triton **model repository**, not a file:

```txt
s3://<bucket>/pipeline/models/<run-id>/model/
└── yolo-plate-detector/
    ├── config.pbtxt
    └── 1/model.onnx
```

Find the run id from the Model Registry, or from `metrics.json` next to it.

## Predict

The endpoint returns YOLO's raw output tensor, **not** boxes — NMS and the box
decode live in ultralytics, not in the ONNX graph. `predict.py` does that work:

```sh
pip install opencv-python-headless numpy
python predict.py car.jpeg
```

Run it from inside the cluster; the predictor is a ClusterIP service.

## Notes

- **Credentials.** The storage-initializer reads S3 as `default-editor`, which
  carries the S3 role by EKS Pod Identity (`infra/60-s3-iam.tf`). No access
  keys are stored anywhere.
- **CPU by default.** The graph has a fixed batch of 1 and the model is small,
  so a GPU node is not worth its Karpenter provisioning wait. The manifest has
  the GPU placement commented out if you want it.
- **`RawDeployment`.** Avoids Knative scale-to-zero, which would release the
  node and pay the provisioning wait again on the next request.
- **Batch is fixed at 1.** `max_batch_size: 0` in `config.pbtxt`, because the
  export pins the batch dimension. Serving many requests at once means
  re-exporting with `dynamic=True`.
