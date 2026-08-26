# # eks-addon-csi.tf

# # ##############################
# # IAM for the EBS CSI driver addon
# # ##############################
# data "aws_iam_policy_document" "ebs_csi_assume_role" {
#   statement {
#     effect  = "Allow"
#     actions = ["sts:AssumeRole", "sts:TagSession"]

#     principals {
#       type        = "Service"
#       identifiers = ["pods.eks.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "ebs_csi" {
#   name               = "${local.project_prefix}-ebs-csi"
#   assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume_role.json

#   tags = local.project_tags
# }

# resource "aws_iam_role_policy_attachment" "ebs_csi" {
#   role       = aws_iam_role.ebs_csi.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
# }