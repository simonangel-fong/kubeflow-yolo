# eks.tf

module "eks" {
  source = "terraform-aws-modules/eks/aws"
  # Pinned exactly: 21.25.0 requires AWS provider >= 6.59, above our 6.58.0 pin.
  version = "21.24.0"

  name               = "${local.project_prefix}-eks"
  kubernetes_version = local.eks_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Public endpoint so kubectl/ArgoCD can reach the API from outside the VPC.
  endpoint_public_access  = true
  endpoint_private_access = true

  # Grants the applying principal cluster-admin, otherwise kubectl is locked out.
  enable_cluster_creator_admin_permissions = true

  addons = {
    coredns                = {}
    eks-pod-identity-agent = {}
    kube-proxy             = {}
    metrics-server         = {}

    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }

    vpc-cni = {
      # Required for Kubernetes NetworkPolicy enforcement by the VPC CNI.
      configuration_values = jsonencode({
        enableNetworkPolicy = "true"
      })
    }
  }

  eks_managed_node_groups = {
    default = {
      instance_types = [local.eks_node_instance_type]
      ami_type       = "AL2023_x86_64_STANDARD"
      capacity_type  = "ON_DEMAND"

      min_size     = local.eks_node_count
      max_size     = local.eks_node_count
      desired_size = local.eks_node_count

      disk_size = local.eks_node_disk_size
    }
  }

  tags = local.project_tags
}
