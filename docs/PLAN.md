## Stage 4 local cluster

- create local cluster with docker kind
- install argocd using helm
- install kubeflow notebook stack via argocd
- deploy a notebook server

---

## Stack

- docker kind
- argocd
- istio (ambient)
- kubeflow

---

## Phases

| #   | Phase                  | Description                                | Done when                                                          |
| --- | ---------------------- | ------------------------------------------ | ------------------------------------------------------------------ |
| 1   | init cluster           | kind cluster; confirm `data/` mountable    | node Ready; pod reads `/data/raw` (hostPath mount)                 |
| 2   | install argocd         | argocd via helm                            | UI reachable,                                                      |
| 3   | bootstrap app-of-apps  | apply `argocd/root.yaml`                   | root Application `Synced` + `Healthy`                              |
| 4   | cert-manager           | cert-manager via argocd                    | webhook pod Ready                                                  |
| 5   | istio (ambient)        | istiod + ztunnel, ambient mode             | istiod Ready; ztunnel DaemonSet Ready on the node                  |
| 6   | namespace + rbac       | kubeflow namespace, roles, service account | namespace + roles present; namespace in the ambient mesh           |
| 7   | notebook controller    | notebook stack via argocd                  | `Notebook` CRD registered; controller Running                      |
| 8   | create notebook server | notebook server, mount the data            | PVC `Bound`; notebook opens, sees `data/raw/`, imports ultralytics |
| 9   | rebuild rehearsal      | `kind delete` then recreate from git alone | phase 8 reached with no manual steps                               |

---

## Output

`docs/04-local-cluster.md` — write-up of the stage.
