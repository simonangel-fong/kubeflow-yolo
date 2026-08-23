# Kubeflow: Jupyter notebook

[Back](../README.md)

---

## Notebook

```sh
kubectl apply -f kubeflow/notebook/
# notebook.kubeflow.org/yolo-cpu applied
# persistentvolumeclaim/yolo-cpu-workspace applied

kubectl get notebook,pod,pvc -n kubeflow-user-example-com
# NAME                             AGE
# notebook.kubeflow.org/yolo-cpu   3m5s

# NAME                                             READY   STATUS    RESTARTS   AGE
# pod/model-registry-db-86979795c4-v8lwg           1/1     Running   0          58m
# pod/model-registry-deployment-64686c8cbf-prxmd   2/2     Running   0          58m
# pod/model-registry-ui-6cc794669b-7g2vl           2/2     Running   0          58m
# pod/yolo-cpu-0                                   2/2     Running   0          3m5s

# NAME                                       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   VOLUMEATTRIBUTESCLASS   AGE
# persistentvolumeclaim/metadata-postgres    Bound    pvc-33bae81a-ed79-4a69-b011-513b3550da79   10Gi       RWO            gp3            <unset>                 59m
# persistentvolumeclaim/yolo-cpu-workspace   Bound    pvc-684c9663-4b37-4133-972c-2c5b8c6d1dc7   20Gi       RWO            gp3            <unset>                 3m5s

kubectl get pod yolo-cpu-0 -n kubeflow-user-example-com -o wide
# NAME         READY   STATUS    RESTARTS   AGE     IP           NODE                                          NOMINATED NODE   READINESS GATES
# yolo-cpu-0   2/2     Running   0          3m36s   10.0.12.20   ip-10-0-12-37.ca-central-1.compute.internal   <none>           <none>

# provision notebook instance
kubectl apply -f kubeflow/notebook/notebook-cpu.yaml
kubectl apply -f kubeflow/notebook/notebook-gpu.yaml
```

---

## Train model

### Track data

```sh
# install dvc in venv
pip install -r requirements.txt

dvc version
# DVC version: 3.67.1 (pip)

# Initialize
dvc init
# Initialized DVC repository.

# You can now commit the changes to git.

# +---------------------------------------------------------------------+
# |                                                                     |
# |        DVC has enabled anonymous aggregate usage analytics.         |
# |     Read the analytics documentation (and how to opt-out) here:     |
# |             <https://dvc.org/doc/user-guide/analytics>              |
# |                                                                     |
# +---------------------------------------------------------------------+

# What's next?
# ------------
# - Check out the documentation: <https://dvc.org/doc>
# - Get help and share ideas: <https://dvc.org/chat>
# - Star us on GitHub: <https://github.com/treeverse/dvc>

# get bucket id
terraform -chdir=infra output -raw s3_bucket_name
# kubeflow-yolo-dev-099139718958

# Set S3 as Remote Storage
dvc remote add -d s3 s3://kubeflow-yolo-dev-099139718958/data/raw
# Setting 's3' as a default remote.

# track data
dvc add data/raw
# 100% Adding...|███████████████████████████████████████████████████████████████████████████████████████████|1/1 [00:00,  2.37file/s]

# To track the changes with git, run:

#         git add 'data\raw.dvc'

# To enable auto staging, run:

#         dvc config core.autostage true

git add .gitignore data/raw.dvc .dvc/config
git commit -m "dvc: track data/raw"
dvc push
# Collecting                                                                                                   |1.11k [00:01,  985entry/s]
# Pushing
# 1096 files pushed

```

---

### training

```sh
# clone project
git clone https://github.com/simonangel-fong/kubeflow-yolo.git
```

---

## Experiment

Submit from a terminal **inside the notebook** — `OptimizerClient()` reads the
in-cluster service account, so it does not work from a laptop.

```sh
# deps for the submitting process (trials install their own)
pip install kubeflow

# submit
cd ~/kubeflow-yolo/kubeflow/katib
python sweep_sdk.py
# submitted: d9328eb9f65b

# watch from anywhere
kubectl get experiment,trials -n kubeflow-user-example-com
# NAME                                   TYPE      STATUS   AGE
# experiment.kubeflow.org/d9328eb9f65b   Created   True     20s

kubectl get pods -n kubeflow-user-example-com | grep node-0-0
# d9328eb9f65b-84p4wwj8-node-0-0-86rfq         3/3     Running           0          30s
# d9328eb9f65b-r4d5nfdj-node-0-0-2dzcv         1/3     PodInitializing   0          30s

# trial logs; the objective prints `mAP50=<value>` for the collector
kubectl logs -n kubeflow-user-example-com d9328eb9f65b-84p4wwj8-node-0-0-86rfq -c node

# best result once complete
kubectl get experiment d9328eb9f65b -n kubeflow-user-example-com \
  -o jsonpath='{.status.currentOptimalTrial}' | jq

# clean up
kubectl delete experiment d9328eb9f65b -n kubeflow-user-example-com
```

Trials are evicted mid-run if Karpenter consolidates the node under them. The
`general` NodePool uses `consolidateAfter: 15m` for this reason — at the
previous 90s, trials died while still pip-installing.

# katib

# pipeline

```txt
fetch_data -> prepare_data -> train -> evaluate
                                    \-> upload_model
```

---

## One-time setup

`kfp.Client()` authenticates with a projected ServiceAccount token, and the
notebook's default token has the wrong audience. The PodDefault mounts a
correctly scoped one:

```sh
kubectl apply -f kubeflow/notebook/kfp-api-token.yaml

# confirm the token landed
kubectl exec -n kubeflow-user-example-com yolo-cpu-0 -c notebook -- ls /var/run/secrets/kubeflow/pipelines/
# token
```

## Submit

From a terminal **inside the notebook** — `ml-pipeline-ui` is a ClusterIP
service behind istio, so this does not work from a laptop.

```sh
pip install kfp

cd ~/kubeflow-yolo/kubeflow/pipelines
python compile.py
# compiled /home/jovyan/kubeflow-yolo/kubeflow/pipelines/yolo_pipeline.yaml

python submit.py
# run 3f9c1a72-...
# arguments (defaults)

# override hyperparameters, or train against a different dataset version
python submit.py --epochs 10 --lr0 0.005
python submit.py --dvc-dir-hash <md5-from-data/raw.dvc>
```

Watch it from anywhere:

```sh
kubectl get workflows -n kubeflow-user-example-com
kubectl logs -n kubeflow-user-example-com <pod> -c main
```

mAP50 / mAP50-95 / precision / recall land on the run's Metrics tab. The
weights go to `s3://<bucket>/models/<run-id>/best.pt` with a `metrics.json`
alongside, keyed by run id so runs never overwrite each other.

## Notes

- `dvc_dir_hash` is a pipeline parameter, not a constant. It is the md5 of the
  `.dir` manifest in `data/raw.dvc`, so a run is pinned to a dataset version —
  re-running against new data is a parameter change, not a code change.
- S3 access needs no credentials in the pipeline: EKS Pod Identity is
  associated to `default-editor`, which pipeline pods already run as
  (`infra/61-s3-notebook.tf`).
- `fetch_data` is cached, so re-running with the same dataset hash skips the
  download and starts at the split.
- The train step sets `set_retry(num_retries=1)`: Karpenter can still
  consolidate a node out from under a long step, same failure that was killing
  Katib trials.

```sh
kubectl get workflows -n kubeflow-user-example-com --sort-by=.metadata.creationTimestamp


```

# Kubeflow: Pipeline

```txt
prepare_data -> train -> evaluate -> register_model
```

| Step             | Does                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------- |
| `prepare_data`   | Reads the DVC-tracked dataset from S3, splits train/val server-side, writes `data.yaml` |
| `train`          | Fine-tunes `yolo11n.pt` on a GPU node, uploads `best.pt`                                |
| `evaluate`       | Re-validates `best.pt`, logs mAP to the run's Metrics tab                               |
| `register_model` | Exports ONNX, uploads the bundle, registers in Model Registry                           |

Steps pass S3 URIs as strings rather than KFP artifacts, so no data travels
through the artifact store.

## Run

From a terminal **inside the notebook** — `ml-pipeline-ui` is a ClusterIP
service, so this does not work from a laptop.

```sh
pip install kfp kfp-kubernetes

cd ~/kubeflow-yolo/kubeflow/pipelines
python compile.py
python submit.py

# override hyperparameters, or train against a different dataset version
python submit.py --epochs 50 --batch 16
python submit.py --dvc-dir-hash <md5-from-data/raw.dvc>
```

Watch it:

```sh
kubectl get workflows -n kubeflow-user-example-com
kubectl logs -n kubeflow-user-example-com <pod> -c main
```

## Output

Everything for a run lands under one prefix, keyed by run id so runs never
overwrite each other:

```txt
s3://<bucket>/pipeline/models/<run-id>/
├── best.pt
├── metrics.json
├── model.tar.gz          # archive
└── model/model.onnx      # KServe storageUri
```

The model registers as `yolo-plate-detector`, version `<run-id>`.

## Notes

- **GPU.** `train` requests `nvidia.com/gpu: 1` and is sized for a `g5.xlarge`,
  the only instance the `gpu` NodePool provisions. That NodePool taints its
  nodes, so the task carries a matching toleration — without it the pod stays
  Pending and Karpenter never provisions. Expect a few minutes of Pending while
  the node comes up.
- **`dvc_dir_hash` is a parameter, not a constant.** It is the md5 of the
  `.dir` manifest in `data/raw.dvc`, so a run is pinned to a dataset version —
  training against new data is a parameter change, not a code change.
- **Caching.** Steps are cached on their inputs, so re-running with the same
  arguments skips straight to the first thing that changed.
- **The quality gate is commented out** in `yolo_pipeline.py`. Uncomment the
  `dsl.If` around `register_model` once the model clears `min_map50`, or every
  run registers regardless of how it scored.
- **opencv.** `ultralytics` installs GUI opencv over the headless build, and
  `libGL.so.1` is absent from a plain python image, so the steps that import
  ultralytics reinstall headless first.
