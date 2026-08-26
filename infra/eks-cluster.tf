# eks-cluster.tf

# ##############################
# EKS
# ##############################
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.24.0"

  count = var.enable_eks ? 1 : 0

  name               = local.project_prefix
  kubernetes_version = local.eks_version

  vpc_id     = module.vpc[0].vpc_id
  subnet_ids = module.vpc[0].private_subnets

  endpoint_public_access  = true
  endpoint_private_access = true

  enable_cluster_creator_admin_permissions = true

  # add-ons
  addons = {
    coredns = {
      configuration_values = jsonencode({
        tolerations = [
          { key = "workload-class", operator = "Equal", value = "platform", effect = "NoSchedule" },
          { key = "CriticalAddonsOnly", operator = "Exists" },
        ]
      })
    }
    eks-pod-identity-agent = {
      before_compute = true # before node
    }
    kube-proxy = {
      before_compute = true # before note
    }
    metrics-server = {
      configuration_values = jsonencode({
        tolerations = [
          { key = "workload-class", operator = "Equal", value = "platform", effect = "NoSchedule" },
        ]
      })
    }

    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.eks_csi_ebs.arn
        service_account = "ebs-csi-controller-sa"
      }]
      configuration_values = jsonencode({
        controller = {
          tolerations = [
            { key = "workload-class", operator = "Equal", value = "platform", effect = "NoSchedule" },
          ]
        }
      })
    }

    # aws-efs-csi-driver = {
    #   pod_identity_association = [{
    #     role_arn        = aws_iam_role.eks_csi_ebs.arn
    #     service_account = "efs-csi-controller-sa"
    #   }]
    #   configuration_values = jsonencode({
    #     controller = {
    #       tolerations = [
    #         { key = "workload-class", operator = "Equal", value = "platform", effect = "NoSchedule" },
    #       ]
    #     }
    #   })
    # }

    vpc-cni = {
      before_compute = true
      configuration_values = jsonencode({
        enableNetworkPolicy = "true"
      })
    }
  }

  node_security_group_additional_rules = {
    istio_webhook = {
      description                   = "Control plane to istiod webhook"
      protocol                      = "tcp"
      from_port                     = 15017
      to_port                       = 15017
      type                          = "ingress"
      source_cluster_security_group = true
    }
  }

  # node group
  eks_managed_node_groups = {
    bootstrap = {
      instance_types = [local.eks_node_instance_type]
      ami_type       = "AL2023_x86_64_STANDARD"
      capacity_type  = "ON_DEMAND"

      min_size     = local.eks_node_count_min
      max_size     = local.eks_node_count_max
      desired_size = local.eks_node_count_desired

      disk_size = local.eks_node_disk_size

      labels = {
        "role"                    = "bootstrap"
        "workload-class"          = "platform"
        "karpenter.sh/controller" = "true"
      }
      taints = {
        platform = {
          key    = "workload-class"
          value  = "platform"
          effect = "NO_SCHEDULE"
        }
      }

    }
  }

  # Karpenter's EC2NodeClass tag
  node_security_group_tags = {
    "karpenter.sh/discovery" = local.karpenter_discovery
  }

  tags = local.project_tags
}
