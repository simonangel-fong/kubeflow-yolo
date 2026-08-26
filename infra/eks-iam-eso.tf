# eks-iam-eso.tf

# ##############################
# IAM role: ESO
# ##############################
resource "aws_iam_role" "eso" {
  count = var.enable_eks ? 1 : 0

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
  count = var.enable_eks ? 1 : 0

  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.eso_cloudflare[0].arn,
      # aws_secretsmanager_secret.mlflow_postgres.arn,
      # aws_secretsmanager_secret.mlflow_flask_key.arn,
    ]
  }
}

resource "aws_iam_role_policy" "eso" {
  count = var.enable_eks ? 1 : 0

  name   = "${local.project_prefix}-secretsmanager-read"
  role   = aws_iam_role.eso[0].id
  policy = data.aws_iam_policy_document.eso[0].json
}

resource "aws_eks_pod_identity_association" "eso" {
  count = var.enable_eks ? 1 : 0

  cluster_name    = module.eks[0].cluster_name
  namespace       = local.eso_namespace
  service_account = local.eso_service_account
  role_arn        = aws_iam_role.eso[0].arn
}
