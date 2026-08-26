# # s3-iam.tf

# # ##############################
# # IAM: S3
# # ##############################
# data "aws_iam_policy_document" "notebook_s3_assume_role" {
#   statement {
#     effect  = "Allow"
#     actions = ["sts:AssumeRole", "sts:TagSession"]

#     principals {
#       type        = "Service"
#       identifiers = ["pods.eks.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "notebook_s3" {
#   name               = "${local.project_prefix}-notebook-s3"
#   assume_role_policy = data.aws_iam_policy_document.notebook_s3_assume_role.json

#   tags = local.project_tags
# }

# # Scoped to the project bucket only. ListBucket is on the bucket itself while
# # the object actions are on its contents, hence the two separate statements.
# data "aws_iam_policy_document" "notebook_s3" {
#   statement {
#     sid    = "ListProjectBucket"
#     effect = "Allow"
#     actions = [
#       "s3:ListBucket",
#       "s3:GetBucketLocation",
#     ]
#     resources = [aws_s3_bucket.project.arn]
#   }

#   statement {
#     sid    = "ReadWriteProjectObjects"
#     effect = "Allow"
#     actions = [
#       "s3:GetObject",
#       "s3:PutObject",
#       "s3:DeleteObject",
#       "s3:AbortMultipartUpload",
#       "s3:ListMultipartUploadParts",
#     ]
#     resources = ["${aws_s3_bucket.project.arn}/*"]
#   }
# }

# resource "aws_iam_role_policy" "notebook_s3" {
#   name   = "${local.project_prefix}-notebook-s3"
#   role   = aws_iam_role.notebook_s3.id
#   policy = data.aws_iam_policy_document.notebook_s3.json
# }

# # default-editor is the Kubeflow profile service account, so every notebook and
# # pipeline pod in the profile namespace inherits this access.
# resource "aws_eks_pod_identity_association" "notebook_s3" {
#   cluster_name    = module.eks.cluster_name
#   namespace       = local.kubeflow_profile_namespace
#   service_account = local.kubeflow_profile_service_account
#   role_arn        = aws_iam_role.notebook_s3.arn

#   tags = local.project_tags
# }
