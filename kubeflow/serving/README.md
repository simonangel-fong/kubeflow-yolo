# Serving

Serves the model the pipeline registered, using KServe.

`modelFormat: triton` with `protocolVersion: v2` selects `kserve-tritonserver`
(`kubectl get clusterservingruntimes`). `onnx` selects a runtime that expects a
bare model file, not the repository layout below.

## Deploy

Point `storageUri` at the run you want, then apply:

```sh
kubectl apply -f kubeflow/serving/inferenceservice.yaml 
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
- **Opset is pinned to 19.** onnxruntime in the Triton runtime rejects
  ultralytics' default opset 20 with "Opset 20 is under development".
- **The export is verified before it registers.** `register_model` runs the
  served pre/post-processing against the `.pt` on a sample of val images and
  refuses to register when the boxes disagree by more than `max_box_delta_px`
  (default 2px). `python -m inference.export` applies the same gate locally.
- **Batch is fixed at 1.** `max_batch_size: 0` in `config.pbtxt`, because the
  export pins the batch dimension. Serving many requests at once means
  re-exporting with `dynamic=True`.
