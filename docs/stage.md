Stage 1 local train

- train yolo model in venv with notebook

Stage 2 local track

- deploy jupyter notebook and mlflow with docker compose
- train the same model
- track training with mlflow
- try hyperparameter tunning with mlflow

Stage 3 local pipeline(skip)

- build a pipeline to train the model locally using .py files
- run pipeline locally with venv

Stage 4 local cluster

- create local cluster with docker kind
- install argocd using helm
- install kubeflow via argocd
- install Dashboard, notebook

Stage 5 cluster train

- install Trainer
- create trainjob image
- train model with kufeflow trainer with image

Stage cluster track(skip)

- install mlflow in cluster via argocd
- train and track train via mlflow

Stage 6 cluster pipeline(skip)

- install Pipelines (KFP)
- create pipeline in cluster to train the model

Stage 7 cluster serve

- install kserve
- deploy the model

Stage 8 eks init

- create eks cluster
- install apps, notebook

Stage 9 eks train

- train model
- save processed data in s3; train model(with cpu) and save to s3

Stage 9 eks track(skip)

- install mlflow
- trach training

Stage 10 eks pipeline

- train model with pipeline
- fetch dvc data from s3, split, train, evaluate, upload weights to s3

stage 11 eks train (gpu)

- install Katib
- train model with gpu node
- compare in mlflow

stage 12 eks serve

- install kserve
- deploy the model

stage 13 application

- backend & frontend
  - user upload image; response the image with box identifying the plate
