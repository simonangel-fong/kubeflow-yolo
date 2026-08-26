# locals.tf

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
  ecr_repo = ["train", "kserve", "frontend"]

  # ##############################
  # GitHub Actions OIDC
  # ##############################
  github_oidc_host = "token.actions.githubusercontent.com"
  github_oidc_subject = format(
    "repo:%s@%d/%s@%d",
    local.github_owner, local.github_owner_id,
    local.github_repo, local.github_repo_id,
  )

  github_owner    = "simonangel-fong"
  github_owner_id = 64545430
  github_repo     = "kubeflow-yolo"
  github_repo_id  = 1326782654

  # terraform backend; the plan role needs access to both root module states
  github_tf_backend_bucket = "simonangelfong-terraform-backend"
  github_tf_backend_key    = "kubeflow-yolo/${var.env}/"
  github_tf_environment    = "tf-apply"
}
