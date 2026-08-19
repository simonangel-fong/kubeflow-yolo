# outputs

# ##############################
# VPC
# ##############################
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr_block
}

output "vpc_public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnets
}

output "vpc_private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "vpc_azs" {
  description = "Availability zones in use"
  value       = module.vpc.azs
}

# ##############################
# EKS
# ##############################
output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_version" {
  description = "EKS Kubernetes version"
  value       = module.eks.cluster_version
}

output "eks_cluster_security_group_id" {
  description = "Cluster security group created by EKS for control plane / node communication"
  value       = module.eks.cluster_security_group_id
}

output "eks_node_security_group_id" {
  description = "Node security group, for use by node groups added later"
  value       = module.eks.node_security_group_id
}

output "eks_oidc_provider_arn" {
  description = "IRSA OIDC provider ARN"
  value       = module.eks.oidc_provider_arn
}

output "eks_update_kubeconfig" {
  description = "Command to configure kubectl for this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

# ##############################
# ArgoCD
# ##############################
output "argocd_namespace" {
  description = "Namespace ArgoCD is installed into"
  value       = helm_release.argocd.namespace
}

output "argocd_chart_version" {
  description = "Installed ArgoCD chart version"
  value       = helm_release.argocd.version
}

output "argocd_bootstrap" {
  description = "Post-apply steps: fetch admin password, port-forward the UI, apply the app-of-apps root"
  value       = <<-EOT
    kubectl -n ${helm_release.argocd.namespace} get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
    kubectl -n ${helm_release.argocd.namespace} port-forward svc/argocd-server 8080:443
    kubectl apply -f argocd/root.yaml
  EOT
}
