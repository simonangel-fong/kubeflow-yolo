Stage 7 cluster serve

- install kserve
- deploy the model

- create a trainjob image for `src/train.py`, push to Docker Hub
- define a custom TrainingRuntime for single-node YOLO
- train the model as a TrainJob in the cluster

---

## Stack

- kind
- argocd
- kubeflow kserve
- docker hub

---

## Phases

| #   | Phase                                        |
| --- | -------------------------------------------- |
| 0   | Identify trained model; retrain if necessary |
| 1   | transform model format to deploy with kserve |
| 2   | install kserve                               |
| 3   | deploy model with kserve                     |
| 4   | test deployed model                          |

---

## Output

`docs/kubeflow_kserve.md`: write key commands
