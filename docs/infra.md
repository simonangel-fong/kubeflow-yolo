```sh
terraform -chdir=infra init -backend-config=backend.hcl

terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra apply -auto-approve

terraform -chdir=infra refresh
terraform -chdir=infra output

terraform -chdir=infra destroy -auto-approve
```

---

## ArgoCD

```sh
aws eks update-kubeconfig --region ca-central-1 --name kubeflow-yolo-dev
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
kubectl -n argocd port-forward svc/argocd-server 8080:443

kubectl apply -f app-of-apps.yaml
argocd login localhost:8080


kubectl -n argocd patch app/platform-karpenter --type merge -p '{"metadata":{"finalizers":[]}}'

kubectl -n external-secrets rollout restart deploy external-secrets

kubectl -n kube-system rollout restart deploy aws-load-balancer-controller


```

---

