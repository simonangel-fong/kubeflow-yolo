# locals.tf

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  # ##############################
  # Metadata
  # ##############################
  project_name   = "kubeflow-yolo"
  project_prefix = "${local.project_name}-${var.env}"
  project_tags = {
    Name      = local.project_prefix
    Project   = local.project_name
    Env       = var.env
    ManagedBy = "Terraform"
  }

  # ##############################
  # AWS
  # ##############################
  aws_azs = slice(data.aws_availability_zones.available.names, 0, 3)

  # ##############################
  # VPC
  # ##############################
  vpc_cidr = "10.0.0.0/16"
  vpc_public_subnets = {
    for i, az in local.aws_azs : az => cidrsubnet(local.vpc_cidr, 8, i + 100)
  }

  vpc_private_subnets = {
    for i, az in local.aws_azs : az => cidrsubnet(local.vpc_cidr, 8, i + 10)
  }

  # ##############################
  # EKS
  # ##############################
  eks_version = "1.36"

  eks_node_instance_type = "t3.xlarge"
  eks_node_count         = 2
  eks_node_disk_size     = 50

  # ##############################
  # Karpenter
  # ##############################
  karpenter_namespace     = "kube-system"
  karpenter_chart_version = "1.14.0"
  karpenter_discovery = "${local.project_prefix}-eks"

  # ##############################
  # ESO
  # ##############################
  eso_namespace       = "external-secrets"
  eso_service_account = "external-secrets"

  # ##############################
  # ArgoCD
  # ##############################
  argocd_namespace     = "argocd"
  argocd_chart_version = "10.4.0"
}
