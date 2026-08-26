# iam-kubeflow-notebook.tf

# ##############################
# IAM: S3
# ##############################
resource "aws_iam_role" "kubeflow_notebook" {
  name               = "${local.project_prefix}-kubeflow-notebook"
  assume_role_policy = data.aws_iam_policy_document.kubeflow_notebook_assume_role.json

  tags = local.project_tags
}

data "aws_iam_policy_document" "kubeflow_notebook_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "kubeflow_notebook" {
  statement {
    sid    = "ListProjectBucket"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [local.s3_bucket_arn]
  }

  statement {
    sid    = "ReadWriteProjectObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = ["${local.s3_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "kubeflow_notebook" {
  name   = "${local.project_prefix}-notebook-s3"
  role   = aws_iam_role.kubeflow_notebook.id
  policy = data.aws_iam_policy_document.kubeflow_notebook.json
}

resource "aws_eks_pod_identity_association" "kubeflow_notebook" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.kubeflow_profile_namespace
  service_account = local.kubeflow_profile_service_account
  role_arn        = aws_iam_role.kubeflow_notebook.arn

  tags = local.project_tags
}
