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

phase

1. [x] create vpc with aws module

- cidr: 10.0.0.0/16
- enable public subnet

2. [x] create eks with aws module on top of vpc
3. [x] node group
   1. type: t3.xlarge
   2. count: 2
4. [x] add-ons
   1. CoreDNS
   2. kube-proxy
   3. Amazon VPC CNI enable network policy
   4. Metrics Server
   5. csi ebs
5. [x] install argocd with terraform
6. [x] install karpenter with terrform
   1. `terraform-aws-modules/eks/aws//modules/karpenter` — controller IAM (Pod Identity), node IAM role + access entry, spot interruption SQS queue
   2. controller via helm chart into `kube-system`, pinned to the managed node group
   3. subnets and node SG tagged `karpenter.sh/discovery = kubeflow-yolo-<env>-eks` for the EC2NodeClass selectors
7. [ ] install karpenter manifest with argocd
   1. type: t5
