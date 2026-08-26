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
  eks_version            = "1.36"
  eks_node_instance_type = "t3.large"
  eks_node_count_desired = 2
  eks_node_count_min     = 2
  eks_node_count_max     = 5
  eks_node_disk_size     = 50

  # ##############################
  # Karpenter
  # ##############################
  karpenter_namespace     = "kube-system"
  karpenter_chart_version = "1.14.0"
  karpenter_discovery     = local.project_prefix

  # ##############################
  # S3
  # ##############################
  s3_bucket_name = "${local.project_prefix}-${data.aws_caller_identity.current.account_id}"
  s3_bucket_prefix = [
    "dvcstore/", # raw data
    "pipeline/processed/",
    "pipeline/runs/",
    "mlflow/", # mlflow tracking artifacts
  ]

  # ##############################
  # ECR
  # ##############################
  ecr_repositories = ["kserve", "frontend", "train"]

  # ##############################
  # GitHub Actions OIDC
  # ##############################
  github_oidc_host = "token.actions.githubusercontent.com"

  # Repositories created on or after 2026-07-15 emit an "immutable" sub claim
  # that appends the permanent numeric owner and repository IDs, so a recycled
  # name cannot mint tokens matching a stale trust policy. This repo was
  # created 2026-08-07, so the name-only form never matches.
  #   gh api repos/<owner>/<repo> --jq '{owner_id:.owner.id, repo_id:.id}'
  github_owner    = "simonangel-fong"
  github_owner_id = 64545430
  github_repo     = "kubeflow-yolo"
  github_repo_id  = 1326782654

  # Mirrors infra/backend.hcl, which is gitignored and so unavailable to the
  # CI role policies below.
  tf_backend_bucket = "simonangelfong-terraform-backend"
  tf_backend_key    = "kubeflow-yolo/dev/terraform.tfstate"

  # GitHub Environment gating terraform apply; must carry required reviewers.
  tf_apply_environment = "tf-apply"

  github_oidc_subject = format(
    "repo:%s@%d/%s@%d",
    local.github_owner, local.github_owner_id,
    local.github_repo, local.github_repo_id,
  )

  # ##############################
  # Kubeflow
  # ##############################
  kubeflow_profile_namespace       = "kubeflow-yolo"
  kubeflow_profile_service_account = "default-editor"

  # ##############################
  # ESO
  # ##############################
  eso_namespace       = "external-secrets"
  eso_service_account = "external-secrets"

  # ##############################
  # ArgoCD
  # ##############################
  argocd_release       = "argocd"
  argocd_chart         = "argo-cd"
  argocd_repo          = "https://argoproj.github.io/argo-helm"
  argocd_chart_version = "10.4.0"
  argocd_namespace     = "argocd"

  argocd_values = yamlencode({
    global = {
      tolerations = [
        {
          key      = "workload-class"
          operator = "Equal"
          value    = "platform"
          effect   = "NoSchedule"
        },
      ]
    }
    server = {
      service = {
        type = "ClusterIP"
      }
      extensions = {
        enabled = true
        contents = [
          {
            name = "rollout-extension"
            url  = "https://github.com/argoproj-labs/rollout-extension/releases/download/v0.3.7/extension.tar"
          }
        ]
      }
    }
  })

  # ##############################
  # AWS Load Balancer Controller
  # ##############################
  albc_namespace       = "kube-system"
  albc_service_account = "aws-load-balancer-controller"

  # ##############################
  # MLflow
  # ##############################
  mlflow_namespace       = "kubeflow"
  mlflow_service_account = "mlflow"
  mlflow_s3_prefix       = "mlflow/"

}
