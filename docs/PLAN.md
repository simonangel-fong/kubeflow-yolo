## Stage 4 local cluster

- create local cluster with docker kind
- install argocd using helm
- install kubeflow via argocd
- install notebook

---

## Stack

- docker kind
- argocd
- kubeflow

---

## Constraints

Docker has **7.6 GB RAM** and the host **30.8 GB free disk**. Full Kubeflow
expects 16+ GB. Install the notebook stack only, not the whole platform, and
raise the Docker memory limit before starting.

---

## Phases

| #   | Phase             | Description                                | Done when                                            |
| --- | ----------------- | ------------------------------------------ | ---------------------------------------------------- |
| 0   | raise docker RAM  | Docker Desktop limit to 12 GB+             | `docker info` shows the new total                    |
| 1   | init cluster      | init cluster with docker kind              | `kubectl get nodes` Ready                            |
| 2   | install argocd    | install argocd with helm                   | UI reachable, `argocd` CLI logged in                 |
| 3   | install kubeflow  | notebook stack via argocd, from a git repo | Application `Synced` + `Healthy`                     |
| 4   | install notebook  | create a notebook server, mount the data   | notebook opens, sees `data/raw/`, imports ultralytics |

### Notes

- **Scope kubeflow down.** Install `kubeflow-notebooks` (plus its dependencies),
  not the full manifest. Pipelines arrive in stage 6, serving in stage 7 —
  installing them now costs memory for nothing.
- **ArgoCD needs a git repo it can read.** It syncs from a repo, not from local
  files, so the manifests must be pushed before phase 3 works.
- **Decide data access in phase 4, not after.** A kind cluster cannot see the
  host filesystem unless the node is configured with `extraMounts` at creation
  time — a phase 1 decision.
- Watch the kind node's disk: images for the notebook stack are several GB.

---

## Output

`docs/04-local-cluster.md` — write-up of the stage.
