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
# NAME                  TYPE      STATUS   AGE
# kubeflow-yolo-plate   Running   True     5m47s

# trials and their pods
kubectl -n kubeflow-yolo get trials
# NAME                           TYPE      STATUS   AGE
# kubeflow-yolo-plate-28rcrkxh   Running   True     96s
# kubeflow-yolo-plate-rj6wg26l   Running   True     96s

kubectl -n kubeflow-yolo get pods -l katib.kubeflow.org/experiment=kubeflow-yolo-plate
# NAME                                                        READY   STATUS    RESTARTS   AGE
# kubeflow-yolo-plate-28rcrkxh-x9frd                          2/2     Running   0          2m55s
# kubeflow-yolo-plate-bayesianoptimization-68b7769569-ngvqh   1/1     Running   0          3m36s
# kubeflow-yolo-plate-rj6wg26l-vcvgj                          2/2     Running   0          2m55s

k get job -n kubeflow-yolo
# NAME                           STATUS     COMPLETIONS   DURATION   AGE
# kubeflow-yolo-plate-28rcrkxh   Running    0/1           4m48s      4m48s
# kubeflow-yolo-plate-rj6wg26l   Running    0/1           4m48s      4m48s
```

---

```sh
# clean up when finished
kubectl -n kubeflow-yolo delete experiment kubeflow-yolo-plate
```
