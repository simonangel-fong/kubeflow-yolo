# github-oidc.tf

# OIDC provider: GitHub Actions
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# ##############################
# Policy: trust identity - general
# ##############################
data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "${local.github_oidc_host}:sub"
      values   = ["${local.github_oidc_subject}:*"]
    }
  }
}

# ##############################
# Policy: trust identity - tf apply
# ##############################
data "aws_iam_policy_document" "github_actions_trust_terraform_apply" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values   = ["${local.github_oidc_subject}:environment:${local.github_tf_environment}"]
    }
  }
}

# ##############################
# IAM role: GitHub Actions ECR push
# ##############################
resource "aws_iam_role" "github_ecr_push" {
  name               = "${local.project_prefix}-github-ecr-push"
  description        = "Assumed by GitHub Actions via OIDC to push application images to ECR"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

# Policy: allow ecr push
data "aws_iam_policy_document" "github_ecr_push" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      # buildx reads existing layers back when pushing.
      "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:ListImages",
    ]
    resources = [for r in aws_ecr_repository.yolo : r.arn]
  }
}

resource "aws_iam_role_policy" "github_ecr_push" {
  name   = "${local.project_prefix}-ecr-push"
  role   = aws_iam_role.github_ecr_push.id
  policy = data.aws_iam_policy_document.github_ecr_push.json
}


# ##############################
# IAM role: Terraform plan
# ##############################
resource "aws_iam_role" "github_terraform_plan" {
  name               = "${local.project_prefix}-github-terraform-plan"
  description        = "Assumed by GitHub Actions to run terraform plan; read-only outside the state bucket"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust_terraform_apply.json
}

# Policy: read only
resource "aws_iam_role_policy_attachment" "github_terraform_plan" {
  role       = aws_iam_role.github_terraform_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Policy: all terraform remote s3
data "aws_iam_policy_document" "github_terraform_plan" {
  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.github_tf_backend_bucket}"]
  }

  statement {
    sid = "StateObject"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${local.github_tf_backend_bucket}/${local.github_tf_backend_key}*"]
  }
}

resource "aws_iam_role_policy" "github_terraform_plan" {
  name   = "${local.project_prefix}-terraform-state"
  role   = aws_iam_role.github_terraform_plan.id
  policy = data.aws_iam_policy_document.github_terraform_plan.json
}

# ##############################
# IAM role: Terraform apply
# ##############################
resource "aws_iam_role" "github_terraform_apply" {
  name               = "${local.project_prefix}-github-terraform-apply"
  description        = "Assumed by the gated ${local.github_tf_environment} environment to run terraform apply"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust_terraform_apply.json
}

resource "aws_iam_role_policy_attachment" "github_terraform_apply_admin" {
  role       = aws_iam_role.github_terraform_apply.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
