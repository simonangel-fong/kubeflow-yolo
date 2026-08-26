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

# ##############################
# IAM role: Terraform plan (read-only)
# ##############################
# Assumed by pull_request runs. Read-only on AWS, plus the state bucket writes
# terraform needs for its lock. Safe to expose to fork-less PR builds.
data "aws_iam_policy_document" "github_terraform_plan_trust" {
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

data "aws_iam_policy_document" "github_terraform_state" {
  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.tf_backend_bucket}"]
  }

  # use_lockfile keeps the lock next to the state object, so plan needs write
  # here even though it changes no infrastructure.
  statement {
    sid = "StateObject"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["arn:aws:s3:::${local.tf_backend_bucket}/${local.tf_backend_key}*"]
  }
}

resource "aws_iam_role" "github_terraform_plan" {
  name               = "${local.project_prefix}-github-terraform-plan"
  description        = "Assumed by GitHub Actions to run terraform plan; read-only outside the state bucket"
  assume_role_policy = data.aws_iam_policy_document.github_terraform_plan_trust.json
}

resource "aws_iam_role_policy_attachment" "github_terraform_plan_readonly" {
  role       = aws_iam_role.github_terraform_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy" "github_terraform_plan_state" {
  name   = "${local.project_prefix}-terraform-state"
  role   = aws_iam_role.github_terraform_plan.id
  policy = data.aws_iam_policy_document.github_terraform_state.json
}

# ##############################
# IAM role: Terraform apply (admin)
# ##############################
# This config manages EKS, VPC, IAM, KMS, S3 and Secrets Manager, so apply is
# effectively account admin. It is therefore restricted twice: the trust policy
# accepts only the `tf-apply` GitHub Environment, and that environment carries
# required reviewers. Narrow this to a permission boundary if the blast radius
# ever needs to shrink further.
data "aws_iam_policy_document" "github_terraform_apply_trust" {
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

    # Not a wildcard: only a job running in the protected environment can
    # assume this role, so a push to any branch cannot reach it.
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values   = ["${local.github_oidc_subject}:environment:${local.tf_apply_environment}"]
    }
  }
}

resource "aws_iam_role" "github_terraform_apply" {
  name               = "${local.project_prefix}-github-terraform-apply"
  description        = "Assumed by the gated ${local.tf_apply_environment} environment to run terraform apply"
  assume_role_policy = data.aws_iam_policy_document.github_terraform_apply_trust.json
}

resource "aws_iam_role_policy_attachment" "github_terraform_apply_admin" {
  role       = aws_iam_role.github_terraform_apply.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
