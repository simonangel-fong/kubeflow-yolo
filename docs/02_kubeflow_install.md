# Kubeflow: Installation

[Back](../README.md)

- [Kubeflow: Installation](#kubeflow-installation)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Install](#install)

---

## Installation

### Prerequisites

```sh
# eks init
terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra apply -auto-approve

# kubeconfig update
aws eks update-kubeconfig --region ca-central-1 --name kubeflow-yolo-dev

# install app with argocd
kubectl apply app-of-apps.yaml

# confirm storageclass
k get storageclass
# NAME            PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
# gp2             kubernetes.io/aws-ebs   Delete          WaitForFirstConsumer   false                  61m
# gp3 (default)   ebs.csi.aws.com         Delete          WaitForFirstConsumer   true                   54m
# gp3-iops        ebs.csi.aws.com         Retain          WaitForFirstConsumer   true                   43m
```

---

### Install

```sh
# clone
git clone https://github.com/kubeflow/community-distribution.git
# checkout latest release branch

cd community-distribution
git checkout release-26.03.1

# install
while ! kustomize build example | kubectl apply --server-side --force-conflicts -f -; do echo "Retrying to apply resources"; sleep 20; done

# confirm
kubectl get pods -n cert-manager
# NAME                                       READY   STATUS    RESTARTS   AGE
# cert-manager-69c7fcbf78-98x27              1/1     Running   0          29m
# cert-manager-cainjector-69f8c8cdbf-dwwqk   1/1     Running   0          29m
# cert-manager-webhook-84fd89df64-5qxph      1/1     Running   0          29m


kubectl get pods -n istio-system
# NAME                                     READY   STATUS    RESTARTS   AGE
# cluster-local-gateway-869bffccbb-kgf5h   1/1     Running   0          30m
# istio-ingressgateway-79449c5b89-gnf9k    1/1     Running   0          30m
# istiod-7dbc4c9576-lt6bc                  1/1     Running   0          30m

kubectl get pods -n auth
# NAME                   READY   STATUS    RESTARTS   AGE
# dex-6b44d9d8d8-b8l67   1/1     Running   0          5m53s
# dex-6b44d9d8d8-jvh4l   1/1     Running   0          5m53s

kubectl get pods -n oauth2-proxy
# NAME                           READY   STATUS    RESTARTS   AGE
# oauth2-proxy-c77dcb7f8-8szsh   1/1     Running   0          5m59s
# oauth2-proxy-c77dcb7f8-w2nkz   1/1     Running   0          5m59s

kubectl get pods -n knative-serving
# NAME                                    READY   STATUS    RESTARTS   AGE
# activator-664bfc9bdd-gm2l4              2/2     Running   0          29m
# autoscaler-55647d5956-j984b             2/2     Running   0          29m
# controller-58467d45bb-984sq             2/2     Running   0          29m
# net-istio-controller-55794746c9-rr4kn   2/2     Running   0          29m
# net-istio-webhook-848d4b7d5f-gfv58      2/2     Running   0          29m
# webhook-679db87d6d-xhjnq                2/2     Running   0          29m

kubectl get pods -n kubeflow
# NAME                                                    READY   STATUS    RESTARTS        AGE
# cache-server-cc85b6cc4-cz9k8                            2/2     Running   0               6m46s
# dashboard-7f56dddfc8-j7vg6                              2/2     Running   0               6m46s
# jupyter-web-app-deployment-b8477594d-cdjgn              2/2     Running   0               6m46s
# katib-controller-788f5d4d74-c7sg9                       1/1     Running   0               6m46s
# katib-db-manager-5ff5b5584b-tfh4p                       1/1     Running   1 (4m14s ago)   6m45s
# katib-mysql-9bf558555-qfqls                             1/1     Running   0               6m45s
# katib-ui-6b867d986d-5fjsb                               2/2     Running   0               6m45s
# kserve-controller-manager-5fb7465ffc-xxm96              2/2     Running   0               6m45s
# kserve-localmodel-controller-manager-75d4b5d49f-mqvjl   2/2     Running   0               6m45s
# kserve-models-web-application-69cb88b55b-5l6pm          2/2     Running   0               6m44s
# kubeflow-pipelines-profile-controller-85775988f-c9dn6   1/1     Running   0               6m44s
# llmisvc-controller-manager-dd76c8dc7-z5jps              2/2     Running   0               6m43s
# metacontroller-0                                        1/1     Running   0               6m46s
# metadata-envoy-deployment-bb49454b5-xlc6b               1/1     Running   0               6m44s
# metadata-grpc-deployment-84c6f9cf79-mlbkr               2/2     Running   5 (2m30s ago)   6m43s
# metadata-writer-5fb5cff9bd-65s5r                        2/2     Running   0               6m42s
# ml-pipeline-6848b5d4d7-4xk86                            2/2     Running   0               6m42s
# ml-pipeline-persistenceagent-646f88694b-f4lhq           2/2     Running   0               6m42s
# ml-pipeline-scheduledworkflow-f4994d98-fr6wk            2/2     Running   0               6m42s
# ml-pipeline-ui-6f6789c496-t7zxg                         2/2     Running   0               6m42s
# ml-pipeline-viewer-crd-74d9fbf5cd-j6hq5                 2/2     Running   0               6m41s
# ml-pipeline-visualizationserver-787f4cb9f7-bkc6h        2/2     Running   0               6m41s
# model-catalog-postgres-0                                1/1     Running   0               6m46s
# model-catalog-server-5cc8cc7786-g5pfk                   2/2     Running   0               6m40s
# mysql-5b6cf8556-fhmq7                                   2/2     Running   0               6m40s
# notebook-controller-deployment-5dbb765757-4rfw6         2/2     Running   0               6m40s
# poddefaults-webhook-deployment-76569d97d5-k69j2         1/1     Running   0               6m40s
# profiles-deployment-7d78b69f85-c89g6                    3/3     Running   0               6m39s
# pvcviewer-controller-manager-84cf5bcf86-d4s7w           3/3     Running   0               6m39s
# seaweedfs-5f6996f6f-ptskf                               2/2     Running   0               6m39s
# spark-operator-controller-55657d7f89-lrcbw              1/1     Running   0               6m39s
# spark-operator-webhook-769497d65d-nkp46                 1/1     Running   0               6m39s
# tensorboard-controller-deployment-5ff96f87cb-vtkqm      3/3     Running   0               6m38s
# tensorboards-web-app-deployment-d5dcf7785-lfx84         2/2     Running   0               6m38s
# volumes-web-app-deployment-84d6cb98c-9gbh5              2/2     Running   0               6m38s
# workflow-controller-cd549fb55-xpfzq                     2/2     Running   0               6m38s

kubectl get pods -n kubeflow-yolo
# NAME                                         READY   STATUS    RESTARTS   AGE
# model-registry-db-86979795c4-8nb25           1/1     Running   0          27m
# model-registry-deployment-64686c8cbf-564cq   2/2     Running   0          27m
# model-registry-ui-6cc794669b-6crgf           2/2     Running   0          27m

# login ui
# kubeflow
kubectl -n istio-ingress port-forward svc/istio-ingress-istio 8080:80

# ad: http://127.0.0.1:8080/
# default email: user@example.com
# default password: 12341234

```

- dashboard

![kf_dashboar01](./img/kf_dashboar01.png)
