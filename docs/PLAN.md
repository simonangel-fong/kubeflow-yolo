Stage 4 local cluster

- install mlflow
- install kubeflow dashboard

---

## Stack

- kind
- argocd
- kubeflow

---

## Phases

| #   | Phase                                 |
| --- | ------------------------------------- |
| 0   | install kubeflow dashboard via argocd |
| 1   | install mlflow ia argocd              |
| 2   | connect notebook with mlflow          |
| 3   | smoke test: 10images 10 epoch         |

---

## Output

`docs/kubeflow_kserve.md`: write key commands
