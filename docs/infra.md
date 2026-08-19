

```sh
terraform -chdir=infra init -backend-config=backend.hcl

terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra apply -auto-approve

terraform -chdir=infra refresh
terraform -chdir=infra output
```

---

phase
1. create vpc with aws module
- cidr: 10.0.0.0/16
- enable public subnet

2. create eks with aws module on top of vpc
3. node group
   1. type: t3.xlarge
   2. count: 2
4. add-ons
   1. CoreDNS
   2. kube-proxy
   3. Amazon VPC CNI enable network policy
   4. Metrics Server
   5. csi ebs
   5. csi ebs
5. install argocd with terraform
6. install karpenter with terrform
7. install karpenter manifest
   1. type: t5
