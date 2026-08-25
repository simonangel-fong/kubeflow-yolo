# Kubeflow: Katib

[Back](../README.md)

- [Kubeflow: Katib](#kubeflow-katib)
  - [Katib](#katib)
    - [Build and push to ECR](#build-and-push-to-ecr)
    - [Run the experiment](#run-the-experiment)

---

## Katib

### Build and push to ECR

```sh
terraform -chdir=infra output
# ecr_repository_urls = {
#   "frontend" = "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-frontend"
#   "kserve" = "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve"
#   "train" = "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-train"
# }

# login
aws ecr get-login-password --region ca-central-1 | docker login --username AWS --password-stdin 099139718958.dkr.ecr.ca-central-1.amazonaws.com

# build: GPU version
docker build -f train-job/Dockerfile -t kubeflow-yolo-train:v0.1.0 .
# build: cpu version
docker build -f train-job/Dockerfile --build-arg FLAVOR=cpu --build-arg BASE=python:3.12-slim -t kubeflow-yolo-train:v0.1.0-cpu .

# tag
docker tag kubeflow-yolo-train:v0.1.0 099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-train:v0.1.0

# push
docker push 099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-train:v0.1.0

# confirm
aws ecr list-images --repository-name kubeflow-yolo-train --region ca-central-1
```

### Run the experiment

```sh
# experiments in the profile namespace
kubectl -n kubeflow-yolo get experiments

# trials and their pods
kubectl -n kubeflow-yolo get trials
kubectl -n kubeflow-yolo get pods -l katib.kubeflow.org/experiment=yolo-plate-hpo
```

---

```sh
# what a trial actually reported
kubectl -n kubeflow-yolo logs job/<trial-name> | tail -5

# the winning assignment
kubectl -n kubeflow-yolo get experiment yolo-plate-hpo -o jsonpath='{.status.currentOptimalTrial}' | python -m json.tool

# clean up when finished -- trial pods are retained for their logs
kubectl -n kubeflow-yolo delete experiment yolo-plate-hpo
```
