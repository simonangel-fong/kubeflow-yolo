# ecr.tf

# ##############################
# ECR: application images
# ##############################
resource "aws_ecr_repository" "yolo" {
  for_each = toset(local.ecr_repo)

  name = "${local.project_name}-${each.key}"
  image_scanning_configuration {
    scan_on_push = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "yolo" {
  for_each = aws_ecr_repository.yolo

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
