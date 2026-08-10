# Deploy the trained model

From `best.pt` to a running inference endpoint.

## Why ONNX

The `.pt` checkpoint needs torch and ultralytics at serving time — roughly 2 GB
of image for a 10 MB model. ONNX drops both: `onnxruntime` loads the graph, and
the pre/post-processing is a few hundred lines of numpy.

The cost is that the exported graph is *only* the network. Ultralytics'
letterbox resize, normalization, NMS and coordinate rescaling stay behind in the
Python wrapper, so [serve/inference.py](../serve/inference.py) reimplements them.
Skipping the letterbox and using a plain resize is the usual cause of "the model
works but the boxes are in the wrong place".

## 1. Export

```bash
python -m serve.export                 # runs/local-train/weights/best.pt
python -m serve.export --no-register   # skip the MLflow step
```

Writes `best.onnx` (10.5 MB) plus `best.metadata.json` carrying `imgsz` and the
class names — the ONNX graph does not record either, and the predictor needs
both to label boxes and size its input.

`--imgsz` must match training (416 here). A mismatch does not raise; it quietly
degrades accuracy.

## 2. Verify parity before deploying

Compare the numpy path against ultralytics on real images. On the six-image
sample the two agree on detection count with a worst-case box delta of 1.21 px
and confidence within 0.07 — the residual is fp32 op ordering and resize
rounding, not a logic difference.

## 3. Build the predictor

```bash
docker build -f serve/Dockerfile -t simonangelfong/kubeflow-yolo-serve:v0.1.0 .
docker push simonangelfong/kubeflow-yolo-serve:v0.1.0
```

Test it locally against a directory holding `model.onnx` and
`model.metadata.json`:

```bash
docker run --rm -p 8080:8080 -v /abs/path/to/model:/mnt/models:ro \
  simonangelfong/kubeflow-yolo-serve:v0.1.0

curl localhost:8080/v1/models/yolo-car-plate
```

On Windows the mount must be a real Windows path — Git Bash's `/tmp` is not
shared with Docker Desktop and silently mounts empty.

## 4. Predict

KServe V1 protocol, base64 image in, detections out:

```bash
python -c "import base64,json;b=base64.b64encode(open('data/raw/some.jpeg','rb').read()).decode();json.dump({'instances':[{'image':{'b64':b}}]},open('req.json','w'))"

curl -X POST localhost:8080/v1/models/yolo-car-plate:predict \
  -H 'Content-Type: application/json' -d @req.json
```

```json
{"predictions":[{"detections":[{"class_id":0,"class_name":"car_plate",
  "confidence":0.5112,"box":{"x1":592.77,"y1":152.61,"x2":635.01,"y2":176.46}}],
  "count":1}]}
```

Per-request `conf` and `iou` overrides are accepted on each instance.

## 5. Deploy to the cluster

[argocd/manifests/serve/inferenceservice.yaml](../argocd/manifests/serve/inferenceservice.yaml)
defines the InferenceService; app `13-serve` syncs it at wave 12.

**KServe must be installed first.** The current ArgoCD waves stop at the trainer
(wave 10) and train (wave 11) — there is no KServe app yet, so `13-serve` will
fail to sync until one is added ahead of it.

`RawDeployment` mode is deliberate: kind has no load balancer, and Knative's
scale-to-zero means a cold start on every demo request.

### Model source

`STORAGE_URI` currently points at `pvc://yolo-train/artifacts/model`. To serve
from the MLflow registry instead, point it at the model version's artifact URI —
which requires the tracking server reachable in-cluster and its artifact store
readable by the storage initializer. The PVC route avoids that coupling and
reuses the volume the TrainJob already writes to.