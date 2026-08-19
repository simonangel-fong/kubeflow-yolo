# locals.tf

locals {
  # ##############################
  # Metadata
  # ##############################
  project_name = "sagemaker-yolo"
  prefix_name  = "${local.project_name}-${var.env}"
  default_tags = {
    Project   = local.project_name
    Env       = var.env
    ManagedBy = "Terraform"
  }
}
