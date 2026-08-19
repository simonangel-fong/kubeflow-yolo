# eks.tf


# ##############################
# IAM for the EBS CSI driver addon
# ##############################
data "aws_iam_policy_document" "ebs_csi_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${local.project_prefix}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume_role.json

  tags = local.project_tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# ##############################
# KES
# ##############################
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.24.0"

  name               = "${local.project_prefix}-eks"
  kubernetes_version = local.eks_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  endpoint_public_access  = true
  endpoint_private_access = true

  enable_cluster_creator_admin_permissions = true

  addons = {
    coredns = {}
    eks-pod-identity-agent = {
      before_compute = true # before node
    }
    kube-proxy = {
      before_compute = true # before note
    }
    metrics-server = {}

    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }

    vpc-cni = {
      before_compute = true
      configuration_values = jsonencode({
        enableNetworkPolicy = "true"
      })
    }
  }

  # node group
  eks_managed_node_groups = {
    bootstrap = {
      instance_types = [local.eks_node_instance_type]
      ami_type       = "AL2023_x86_64_STANDARD"
      capacity_type  = "ON_DEMAND"

      min_size     = local.eks_node_count
      max_size     = local.eks_node_count
      desired_size = local.eks_node_count

      disk_size = local.eks_node_disk_size
    }
  }

  # Karpenter's EC2NodeClass tag
  node_security_group_tags = {
    "karpenter.sh/discovery" = local.karpenter_discovery
  }

  tags = local.project_tags
}
