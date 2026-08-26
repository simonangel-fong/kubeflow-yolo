# outputs

# ##############################
# S3
# ##############################
# Consumed by the cluster root module via terraform_remote_state.
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
output "ecr_repository_urls" {
  description = "Registry URL per application image repository"
  value       = { for k, r in aws_ecr_repository.yolo : k => r.repository_url }
}

# ##############################
# GitHub Actions
# ##############################
output "github_ecr_push_role_arn" {
  description = "Role GitHub Actions assumes to push ecr via OIDC."
  value       = aws_iam_role.github_ecr_push.arn
}

output "github_terraform_plan_role_arn" {
  description = "Role the terraform plan job assumes; set as the TF_PLAN_ROLE_ARN variable"
  value       = aws_iam_role.github_terraform_plan.arn
}

output "github_terraform_apply_role_arn" {
  description = "Role the gated terraform apply job assumes; set as the TF_APPLY_ROLE_ARN variable"
  value       = aws_iam_role.github_terraform_apply.arn
}
