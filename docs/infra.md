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
aws eks update-kubeconfig --region ca-central-1 --name kubeflow-yolo-dev-eks
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
kubectl -n argocd port-forward svc/argocd-server 8080:443

kubectl apply -f app-of-apps.yaml
argocd login localhost:8080


kubectl -n argocd patch app/platform-karpenter --type merge -p '{"metadata":{"finalizers":[]}}'


{"level":"ERROR","time":"2026-08-19T18:18:50.878Z","logger":"controller","message":"failed detecting cluster endpoint","commit":"2be9554","aws-error-code":"AccessDeniedException","aws-operation-name":"DescribeCluster","aws-request-id":"3ca303fa-e745-48b6-941c-b9be85e377fa","aws-service-name":"EKS","aws-status-code":403,"error":"failed to resolve cluster endpoint, operation error EKS: DescribeCluster, https response error StatusCode: 403, RequestID: 3ca303fa-e745-48b6-941c-b9be85e377fa, api error AccessDeniedException: User: arn:aws:sts::099139718958:assumed-role/KarpenterController-7369051ba8b44e7fb5e584a529/eks-kubeflow-y-karpenter--6406e3bd-adb0-4b23-8e77-88ac3fd5387c is not authorized to perform: eks:DescribeCluster on resource: arn:aws:eks:ca-central-1:099139718958:cluster/multi-tenant-eks-dev because no identity-based policy allows the eks:DescribeCluster action (aws-error-code=AccessDeniedException, aws-operation-name=DescribeCluster, aws-request-id=3ca303fa-e745-48b6-941c-b9be85e377fa, aws-service-name=EKS, aws-status-code=403)"}
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
