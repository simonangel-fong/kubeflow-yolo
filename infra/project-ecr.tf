# ecr.tf

# ##############################
# ECR: application images
# ##############################
resource "aws_ecr_repository" "app" {
  for_each = toset(local.ecr_repositories)

  name = "${local.project_name}-${each.key}"

  # allow terraform destroy
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  # encryption_configuration {
  #   encryption_type = "KMS"
  #   kms_key         = aws_kms_key.yolo.arn
  # }

  # lifecycle {
  #   prevent_destroy = true
  # }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each = aws_ecr_repository.app

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
