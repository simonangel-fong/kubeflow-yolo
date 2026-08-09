```sh
kind create cluster --config kind/cluster.yaml
# Creating cluster "desktop" ...
#  • Ensuring node image (kindest/node:v1.35.0) 🖼  ...
#  ✓ Ensuring node image (kindest/node:v1.35.0) 🖼
#  • Preparing nodes 📦   ...
#  ✓ Preparing nodes 📦
#  • Writing configuration 📜  ...
#  ✓ Writing configuration 📜
#  • Starting control-plane 🕹️  ...
#  ✓ Starting control-plane 🕹️
#  • Installing CNI 🔌  ...
#  ✓ Installing CNI 🔌
#  • Installing StorageClass 💾  ...
#  ✓ Installing StorageClass 💾
# Set kubectl context to "kind-desktop"
# You can now use your cluster with:
# kubectl cluster-info --context kind-desktop

kubectl cluster-info --context kind-desktop
# Kubernetes control plane is running at https://127.0.0.1:9981
# CoreDNS is running at https://127.0.0.1:9981/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

# To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.


# Have a nice day! 👋

# confirm cluster
kubectl get node
# NAME                    STATUS   ROLES           AGE     VERSION
# desktop-control-plane   Ready    control-plane   2m27s   v1.35.0

# ##############################
# Confirm mountable
# ##############################
kubectl apply -f kind/mount-check.yaml
# pod/mount-check created

kubectl logs mount-check
# total 200960
# drwxrwxrwx    1 root     root           512 Aug  8 02:05 .
# drwxrwxrwx    1 root     root           512 Aug  8 18:21 ..
# -rwxrwxrwx    1 root     root         76060 Aug  7 16:27 audi_a3_convertible_with_license_plate_11.jpeg
# -rwxrwxrwx    1 root     root            76 Aug  7 16:27 audi_a3_convertible_with_license_plate_11.txt

kubectl delete -f kind/mount-check.yaml
# pod "mount-check" deleted from default namespace

```

---

## Install ArgoCD

```sh
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update argo

helm search repo argo/argo-cd
# NAME            CHART VERSION   APP VERSION     DESCRIPTION
# argo/argo-cd    10.1.4          v3.4.5          A Helm chart for Argo CD, a declarative, GitOps...

helm install argocd argo/argo-cd --version 10.3.0 --namespace argocd --create-namespace -f kind/argocd-values.yaml --wait --timeout 10m

# confirm
kubectl get pods -n argocd
# NAME                                                READY   STATUS    RESTARTS   AGE
# argocd-application-controller-0                     1/1     Running   0          12m
# argocd-applicationset-controller-76cf4f7f59-cf2t5   1/1     Running   0          12m
# argocd-redis-6744cf7696-rntxf                       1/1     Running   0          12m
# argocd-repo-server-66b9bbbc5b-2mk9v                 1/1     Running   0          12m
# argocd-server-55bb599c74-ptl8k                      1/1     Running   0          12m

# access
kubectl port-forward -n argocd svc/argocd-server 8000:80
# Forwarding from 127.0.0.1:8000 -> 8080
# Forwarding from [::1]:8000 -> 8080

# initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# argocd login 127.0.0.1:8000 --username admin --insecure --plaintext
# argocd cluster list
# argocd app list
```

UI at http://127.0.0.1:8081.

---

## ArgoCD

```sh
kubectl apply -f argocd/root.yaml
```
