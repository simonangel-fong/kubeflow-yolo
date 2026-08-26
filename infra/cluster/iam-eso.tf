# iam-eso.tf

# ##############################
# IAM role: ESO
# ##############################
resource "aws_iam_role" "eso" {
  name               = "${local.project_prefix}-eso"
  assume_role_policy = data.aws_iam_policy_document.eso_assume_role.json
}

data "aws_iam_policy_document" "eso_assume_role" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "eso" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.eso_cloudflare.arn,
      aws_secretsmanager_secret.grafana_admin.arn,
      aws_secretsmanager_secret.mlflow_postgres.arn,
      aws_secretsmanager_secret.mlflow_flask_key.arn,
    ]
  }
}

resource "aws_iam_role_policy" "eso" {
  name   = "${local.project_prefix}-secretsmanager-read"
  role   = aws_iam_role.eso.id
  policy = data.aws_iam_policy_document.eso.json
}

resource "aws_eks_pod_identity_association" "eso" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.eso_namespace
  service_account = local.eso_service_account
  role_arn        = aws_iam_role.eso.arn
}
