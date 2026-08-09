
```sh

# ##############################
# cpu version
# ##############################
# build image
docker build -f trainjob/Dockerfile -t simonangelfong/kubeflow-yolo-train:v0.1.0-cpu .

# test local
docker run --rm -v "./data:/data:ro" -v "./runs/docker-test:/workspace" simonangelfong/kubeflow-yolo-train:v0.1.0-cpu --raw /data/raw --processed workspace/processed --data-yaml /workspace/data.yaml --project /workspace/runs --artifacts /workspace/artifacts --limit 20 --epochs 1

# push
docker login
docker push simonangelfong/kubeflow-yolo-train:v0.1.0-cpu

```