## Stage 5 cluster train

- create a trainjob image for `src/train.py`, push to Docker Hub
- define a custom TrainingRuntime for single-node YOLO
- train the model as a TrainJob in the cluster

---

## Stack

- kind
- argocd
- kubeflow trainer v2 (installed in stage 4)
- docker hub

---

## Phases

| #   | Phase                                                            |
| --- | ---------------------------------------------------------------- |
| 0   | trainer installed — done in stage 4                              |
| 1   | build `docker/train.Dockerfile`, test locally, push `:v0.1.0`    |
| 2   | `argocd/manifests/train/` — PVC, TrainingRuntime, TrainJob;      |
|     | synced by `argocd/apps/12-train.yaml`                            |
| 3   | run a `--limit` smoke job, then a full train; check metrics      |

---

## Output

`docs/cluster_train.md` — write-up of the stage.
