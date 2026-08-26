# # eks-iam-mlflow.tf

# # ##############################
# # IAM role: MLflow artifact store
# # ##############################
# data "aws_iam_policy_document" "mlflow_trust" {
#   statement {
#     actions = ["sts:AssumeRole", "sts:TagSession"]
#     principals {
#       type        = "Service"
#       identifiers = ["pods.eks.amazonaws.com"]
#     }
#   }
# }

# data "aws_iam_policy_document" "mlflow_s3" {
#   # Listing is bucket-scoped, but restricted to the mlflow/ prefix.
#   statement {
#     actions   = ["s3:GetBucketLocation"]
#     resources = [aws_s3_bucket.project.arn]
#   }
#   statement {
#     actions   = ["s3:ListBucket"]
#     resources = [aws_s3_bucket.project.arn]
#     condition {
#       test     = "StringLike"
#       variable = "s3:prefix"
#       values   = ["${local.mlflow_s3_prefix}*"]
#     }
#   }
#   statement {
#     actions = [
#       "s3:GetObject",
#       "s3:PutObject",
#       "s3:DeleteObject",
#     ]
#     resources = ["${aws_s3_bucket.project.arn}/${local.mlflow_s3_prefix}*"]
#   }
# }

# resource "aws_iam_role" "mlflow" {
#   name               = "${local.project_prefix}-mlflow"
#   assume_role_policy = data.aws_iam_policy_document.mlflow_trust.json
# }

# resource "aws_iam_role_policy" "mlflow" {
#   name   = "${local.project_prefix}-mlflow-s3"
#   role   = aws_iam_role.mlflow.id
#   policy = data.aws_iam_policy_document.mlflow_s3.json
# }

# resource "aws_eks_pod_identity_association" "mlflow" {
#   cluster_name    = module.eks.cluster_name
#   namespace       = local.mlflow_namespace
#   service_account = local.mlflow_service_account
#   role_arn        = aws_iam_role.mlflow.arn
# }
