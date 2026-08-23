# Kubeflow: KServe

[Back](../README.md)

- [Kubeflow: KServe](#kubeflow-kserve)
  - [Serving](#serving)
    - [Endpoints](#endpoints)
  - [Image](#image)
    - [Build and test locally](#build-and-test-locally)
    - [Push to ECR](#push-to-ecr)
  - [Deploy](#deploy)
  - [Predict](#predict)
  - [Update the model](#update-the-model)
  - [Troubleshooting](#troubleshooting)

---

## Serving

```txt
s3://<bucket>/pipeline/runs/<run-id>/serve/  ->  storage-initializer  ->  /mnt/models  ->  predictor
```

---

### Endpoints

| Endpoint                         |                                                |
| -------------------------------- | ---------------------------------------------- |
| `GET /healthz`                   | liveness                                       |
| `GET /v1/models/{name}`          | readiness; 503 carries the load error          |
| `POST /v1/models/{name}:predict` | inference; per-instance `conf`/`iou` overrides |

---

## Image

### Build and test locally

`./models` bind-mounts onto `/mnt/models`, the same layout the
storage-initializer produces.

```sh
docker compose -f docker-compose.inference.yml up --build

curl localhost:8081/v1/models/kubeflow-yolo-plate
# {"name":"kubeflow-yolo-plate","ready":true,"imgsz":640,"classes":["car_plate"]}
# http://localhost:3000     UI
```

![local_smoke_test](./img/local_smoke_test.png)

---

### Push to ECR

```sh
terraform -chdir=infra output -raw ecr_kserve_repository_url
# 099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve

aws ecr get-login-password --region ca-central-1 | docker login --username AWS --password-stdin 099139718958.dkr.ecr.ca-central-1.amazonaws.com

docker build -f inference/Dockerfile -t kubeflow-yolo-kserve:v0.1.0-cpu .
docker tag kubeflow-yolo-kserve:v0.1.0-cpu 099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve:v0.1.0-cpu
docker push 099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve:v0.1.0-cpu

# confirm
aws ecr list-images --repository-name kubeflow-yolo-kserve --region ca-central-1
```

---

## Deploy

```sh
# list all run
aws s3 ls s3://kubeflow-yolo-dev-099139718958/pipeline/runs/
# PRE 30b11c6a-2cd0-47df-ac32-5c2eeecb8eb4/
# PRE e5ce38bd-9e24-4b98-af7f-6957d79f1449/
# PRE ef97a3f4-5b5c-4a38-bcf2-ca247accfba2/
# 2026-08-22 23:16:18          0 

# enable ecr access
kubectl patch cm config-deployment -n knative-serving --type merge \
  -p '{"data":{"registries-skipping-tag-resolving":"kind.local,ko.local,dev.local,099139718958.dkr.ecr.ca-central-1.amazonaws.com"}}'

kubectl rollout restart deploy/controller -n knative-serving

kubectl delete inferenceservice kubeflow-yolo-plate -n kubeflow-user-example-com
kubectl apply -f kubeflow/kserve/inferenceservice.yaml
# inferenceservice.serving.kserve.io/kubeflow-yolo-plate created

kubectl get inferenceservice kubeflow-yolo-plate -n kubeflow-user-example-com
# NAME                  URL                                                                        READY   PREV   LATEST   PREVROLLEDOUTREVISION   LATESTREADYREVISION                   AGE
# kubeflow-yolo-plate   http://example.com/serving/kubeflow-user-example-com/kubeflow-yolo-plate   True           100                              kubeflow-yolo-plate-predictor-00001   37s
```

---

## Predict

```sh
kubectl port-forward -n kubeflow-user-example-com svc/kubeflow-yolo-plate-predictor 8082:80

curl localhost:8082/v1/models/kubeflow-yolo-plate
# {"name":"kubeflow-yolo-plate","ready":true,"imgsz":640,"classes":["car_plate"]}

python -c "import base64,json,sys; print(json.dumps({'instances':[{'image':{'b64':base64.b64encode(open(sys.argv[1],'rb').read()).decode()},'conf':0.25}]}))" data/sample.jpg > /tmp/payload.json

curl -s -X POST localhost:8082/v1/models/kubeflow-yolo-plate:predict   -H 'Content-Type: application/json' -d @/tmp/payload.json | python -m json.tool
# {"predictions":[{"detections":[{"class_name":"car_plate","confidence":0.91,...}],"count":1}]}
```

Through the gateway instead:

```sh
kubectl port-forward svc/istio-ingressgateway -n istio-system 8080:80
curl -H "Host: kubeflow-yolo-plate.kubeflow-user-example-com.example.com"   localhost:8080/v1/models/kubeflow-yolo-plate
```

---

## Update the model

Only `STORAGE_URI` changes. Knative keeps the old revision serving until the new
one passes readiness.

```sh
kubectl set env -n kubeflow-user-example-com inferenceservice/kubeflow-yolo-plate   STORAGE_URI=s3://kubeflow-yolo-dev-099139718958/pipeline/runs/<new-run-id>/serve

kubectl get revisions -n kubeflow-user-example-com
```

A new image is a `kubectl set image` on the same isvc, after pushing the tag.

---

## Troubleshooting

```sh
# an S3 failure shows here first
kubectl logs -n kubeflow-user-example-com   -l serving.kserve.io/inferenceservice=kubeflow-yolo-plate -c storage-initializer
```

| Symptom                                    | Cause                                                          |
| ------------------------------------------ | -------------------------------------------------------------- |
| `ImagePullBackOff`                         | node role lacks ECR pull, or the tag was never pushed          |
| init `NoCredentialsError` / `AccessDenied` | Pod Identity association missing, or the isvc names another SA |
| init hangs, then fails on egress           | Istio sidecar started after the init container                 |
| 503 `no .onnx under /mnt/models`           | `STORAGE_URI` points at the run prefix, not its `serve/` child |
| 503 but `/healthz` is 200                  | ONNX load failed; the readiness body carries the exception     |
| detections labelled `"0"`                  | `metadata.json` did not come down beside `model.onnx`          |
