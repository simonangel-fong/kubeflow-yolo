# mlflow.tf
#
# MLflow tracking server: experiment metrics/params during training.
# Backend store is Postgres (in-cluster); artifacts go to s3://<bucket>/mlflow/.
# Model registry and serving stay with Kubeflow — MLflow is tracking only.

# ##############################
# IAM role: MLflow artifact store
# ##############################
data "aws_iam_policy_document" "mlflow_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "mlflow_s3" {
  # Listing is bucket-scoped, but restricted to the mlflow/ prefix.
  statement {
    actions   = ["s3:GetBucketLocation"]
    resources = [aws_s3_bucket.project.arn]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.project.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.mlflow_s3_prefix}*"]
    }
  }
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.project.arn}/${local.mlflow_s3_prefix}*"]
  }
}

resource "aws_iam_role" "mlflow" {
  name               = "${local.project_prefix}-mlflow"
  assume_role_policy = data.aws_iam_policy_document.mlflow_trust.json
}

resource "aws_iam_role_policy" "mlflow" {
  name   = "${local.project_prefix}-mlflow-s3"
  role   = aws_iam_role.mlflow.id
  policy = data.aws_iam_policy_document.mlflow_s3.json
}

resource "aws_eks_pod_identity_association" "mlflow" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.mlflow_namespace
  service_account = local.mlflow_service_account
  role_arn        = aws_iam_role.mlflow.arn
}

# ##############################
# Secret: mlflow postgres credentials
# ##############################
resource "random_password" "mlflow_postgres" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "mlflow_postgres" {
  name = "${module.eks.cluster_name}/mlflow-postgres"
}

resource "aws_secretsmanager_secret_version" "mlflow_postgres" {
  secret_id = aws_secretsmanager_secret.mlflow_postgres.id
  secret_string = jsonencode({
    username = "mlflow"
    password = random_password.mlflow_postgres.result
  })
}

# ##############################
# Secret: mlflow flask session key
# ##############################
# The chart generates this at render time when unset, which means a new key on
# every Argo sync (invalidating sessions). Pin it here and deliver via ESO.
resource "random_password" "mlflow_flask_key" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "mlflow_flask_key" {
  name = "${module.eks.cluster_name}/mlflow-flask-key"
}

resource "aws_secretsmanager_secret_version" "mlflow_flask_key" {
  secret_id     = aws_secretsmanager_secret.mlflow_flask_key.id
  secret_string = jsonencode({ key = random_password.mlflow_flask_key.result })
}
