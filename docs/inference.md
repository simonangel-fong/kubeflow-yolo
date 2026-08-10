# Kubeflow YOLO - Inference

[Back](../README.md)

- [Kubeflow YOLO - Inference](#kubeflow-yolo---inference)
  - [Deployment Pipeline](#deployment-pipeline)
  - [Export and verify](#export-and-verify)
  - [Inference](#inference)
    - [Endpiont desgin](#endpiont-desgin)
    - [Inference](#inference-1)
    - [Frontend](#frontend)
    - [Test](#test)
    - [Clean up](#clean-up)

---

## Deployment Pipeline

```
EXPORT(Model) → BUILD(app) → TEST → PUSH
```

---

## Export and verify

```bash
python -m inference.export --run tune-cpu-556img-640px-ep20
```

Writes `models/<run>.onnx` and `<run>.metadata.json` (imgsz + class names — the
graph stores neither).

Then compares ONNX against the `.pt` on 8 val images using the predictor's own
pre/post-processing. Exit 1 if boxes disagree by more than 2 px.

---

## Inference

### Endpiont desgin

| Endpoint                         |                                                |
| -------------------------------- | ---------------------------------------------- |
| `GET /healthz`                   | liveness                                       |
| `GET /v1/models/{name}`          | readiness; 503 carries the load error          |
| `POST /v1/models/{name}:predict` | inference; per-instance `conf`/`iou` overrides |

---

### Inference

```sh
# build
docker build -f inference/Dockerfile -t simonangelfong/kubeflow-yolo-inference:v0.1.0-cpu .

# push
docker push simonangelfong/kubeflow-yolo-inference:v0.1.0-cpu
```

---

### Frontend

```sh
# build
docker build -f inference/Dockerfile -t simonangelfong/kubeflow-yolo-ui:v0.1.0 .

# push
docker push simonangelfong/kubeflow-yolo-ui:v0.1.0
```

---

### Test

```bash
docker compose -f docker-compose.inference.yml up -d --build

# healthz
curl localhost:8080/healthz
# {"status":"ok"}

# model health
curl localhost:8080/v1/models/yolo-car-plate
# {"name":"yolo-car-plate","ready":true,"imgsz":640,"classes":["car_plate"]}

# convert 1st val image into json to send
python -c "import base64,json,glob;p=sorted(glob.glob('data/processed/val/images/*'))[0];b=base64.b64encode(open(p,'rb').read()).decode();json.dump({'instances':[{'image':{'b64':b}}]},open('req.json','w'))"

# inference
curl.exe -X POST localhost:8080/v1/models/yolo-car-plate:predict -H "Content-Type: application/json" -d "@req.json"
# {"predictions":[{"detections":[{"class_id":0,"class_name":"car_plate","confidence":0.8533,"box":{"x1":264.35,"y1":458.91,"x2":410.6,"y2":516.73}}],"count":1}]}
```

---

### Clean up

```sh
docker compose -f docker-compose.inference.yml down -v
```