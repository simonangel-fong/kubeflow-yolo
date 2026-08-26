# project-github-oidc.tf

# Lets GitHub Actions assume an AWS role via OIDC, so the workflows push to
# ECR without long-lived access keys stored as repo secrets.

# ##############################
# OIDC provider: GitHub Actions
# ##############################
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}


# ##############################
# IAM role: GitHub Actions ECR push
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

    # Scope: current repository; any branch, tag, or environment.
    # Uses the immutable subject form -- see local.github_oidc_subject.
    condition {
      test     = "StringLike"
      variable = "${local.github_oidc_host}:sub"
      values   = ["${local.github_oidc_subject}:*"]
    }
  }
}

data "aws_iam_policy_document" "github_actions_ecr_push" {
  # GetAuthorizationToken is account-wide and cannot be resource-scoped.
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
    resources = [for r in aws_ecr_repository.app : r.arn]
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.project_prefix}-github-actions"
  description        = "Assumed by GitHub Actions via OIDC to push application images to ECR"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

resource "aws_iam_role_policy" "github_actions_ecr_push" {
  name   = "${local.project_prefix}-ecr-push"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr_push.json
}
