# outputs

# ##############################
# VPC
# ##############################
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

# ##############################
# EKS
# ##############################
output "eks_cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_update_kubeconfig" {
  description = "Command to configure kubectl for this cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

# ##############################
# Karpenter
# ##############################
output "karpenter_node_iam_role_name" {
  description = "IAM role assumed by Karpenter-launched nodes; referenced by the EC2NodeClass"
  value       = module.karpenter.node_iam_role_name
}

output "karpenter_queue_name" {
  description = "SQS queue the controller polls for spot interruption notices"
  value       = module.karpenter.queue_name
}

output "karpenter_discovery_tag" {
  description = "Value of karpenter.sh/discovery on subnets and the node security group; use in the EC2NodeClass selectors"
  value       = local.karpenter_discovery
}

# ##############################
# EFS
# ##############################
output "efs_file_system_id" {
  description = "Shared dataset filesystem; referenced by the EFS StorageClass"
  value       = aws_efs_file_system.data.id
}

# ##############################
# ArgoCD
# ##############################
output "argocd_bootstrap" {
  description = "Post-apply steps: fetch admin password, port-forward the UI, apply the app-of-apps root"
  value       = <<-EOT
    kubectl -n ${helm_release.argocd.namespace} get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
    kubectl -n ${helm_release.argocd.namespace} port-forward svc/argocd-server 8080:443
    kubectl apply -f argocd/root.yaml
  EOT
}
