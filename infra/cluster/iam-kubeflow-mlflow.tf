# iam-kubeflow-mlflow.tf

# ##############################
# IAM role: kubeflow MLflow
# ##############################
resource "aws_iam_role" "kubeflow_mlflow" {
  name               = "${local.project_prefix}-kubeflow-mlflow"
  assume_role_policy = data.aws_iam_policy_document.kubeflow_mlflow_assume_role.json
}

data "aws_iam_policy_document" "kubeflow_mlflow_assume_role" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "kubeflow_mlflow_s3" {
  # Listing is bucket-scoped, but restricted to the mlflow/ prefix.
  statement {
    actions   = ["s3:GetBucketLocation"]
    resources = [local.s3_bucket_arn]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [local.s3_bucket_arn]
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
    resources = ["${local.s3_bucket_arn}/${local.mlflow_s3_prefix}*"]
  }
}

resource "aws_iam_role_policy" "kubeflow_mlflow_s3" {
  name   = "${local.project_prefix}-mlflow-s3"
  role   = aws_iam_role.kubeflow_mlflow.id
  policy = data.aws_iam_policy_document.kubeflow_mlflow_s3.json
}

resource "aws_eks_pod_identity_association" "kubeflow_mlflow_s3" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.mlflow_namespace
  service_account = local.mlflow_service_account
  role_arn        = aws_iam_role.kubeflow_mlflow.arn
}
