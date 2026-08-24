# eks-eso.tf

# ##############################
# IAM role: ESO
# ##############################
data "aws_iam_policy_document" "eso_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "eso_read" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.eso_cloudflare.arn,
      aws_secretsmanager_secret.mlflow_postgres.arn,
      aws_secretsmanager_secret.mlflow_flask_key.arn,
    ]
  }
}

resource "aws_iam_role" "eso" {
  name               = "${local.project_prefix}-eso"
  assume_role_policy = data.aws_iam_policy_document.eso_trust.json
}

resource "aws_iam_role_policy" "eso" {
  name   = "${local.project_prefix}-secretsmanager-read"
  role   = aws_iam_role.eso.id
  policy = data.aws_iam_policy_document.eso_read.json
}

resource "aws_eks_pod_identity_association" "eso" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.eso_namespace
  service_account = local.eso_service_account
  role_arn        = aws_iam_role.eso.arn
}

# ##############################
# Secrets: cloudflare-api-token
# ##############################
resource "aws_secretsmanager_secret" "eso_cloudflare" {
  name = "${module.eks.cluster_name}/cloudflare-api-token"
}

resource "aws_secretsmanager_secret_version" "cloudflare" {
  secret_id     = aws_secretsmanager_secret.eso_cloudflare.id
  secret_string = jsonencode({ apiToken = var.cloudflare_api_token })
}

# # ##############################
# # Secrets: slack-webhook
# # ##############################
# resource "aws_secretsmanager_secret" "eso_slack_webhook" {
#   name = "${local.project_prefix}/slack-webhook"
# }

# resource "aws_secretsmanager_secret_version" "slack_webhook" {
#   secret_id     = aws_secretsmanager_secret.eso_slack_webhook.id
#   secret_string = jsonencode({ url = var.slack_webhook_url })
# }

import {
  to       = aws_secretsmanager_secret.mlflow_postgres
  identity = { "arn" = "arn:aws:secretsmanager:ca-central-1:099139718958:secret:kubeflow-yolo-dev/mlflow-postgres-y9zRFb" }
}