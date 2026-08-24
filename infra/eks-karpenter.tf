# eks-karpenter.tf

# ##############################
# Karpenter
# ##############################
module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "21.24.0"

  cluster_name = module.eks.cluster_name

  create_pod_identity_association = true # enable pod id
  namespace                       = local.karpenter_namespace
  service_account                 = "karpenter"

  enable_inline_policy = true

  # Node role
  node_iam_role_use_name_prefix = false
  node_iam_role_name            = "${local.project_prefix}-karpenter-node"
  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  # SQS queue + EventBridge rules
  enable_spot_termination = true

  tags = local.project_tags
}
