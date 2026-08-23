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

output "karpenter_node_iam_role_arn" {
  description = "ARN of the Karpenter node IAM role"
  value       = module.karpenter.node_iam_role_arn
}

output "karpenter_controller_iam_role_arn" {
  description = "ARN of the Karpenter controller IAM role"
  value       = module.karpenter.iam_role_arn
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
# S3
# ##############################
output "s3_bucket_name" {
  description = "Project bucket for datasets, model artifacts and MLflow storage"
  value       = aws_s3_bucket.project.id
}

output "s3_bucket_arn" {
  description = "ARN of the project bucket"
  value       = aws_s3_bucket.project.arn
}

# ##############################
# ECR
# ##############################
output "ecr_kserve_repository_url" {
  description = "Registry URL for the KServe predictor image"
  value       = aws_ecr_repository.kserve.repository_url
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
