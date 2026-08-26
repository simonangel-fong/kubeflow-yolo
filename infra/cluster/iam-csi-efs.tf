# iam-efs.tf

# ##############################
# IAM: EFS CSI driver role
# ##############################
resource "aws_iam_role" "eks_csi_efs" {
  name               = "${local.project_prefix}-csi-efs"
  assume_role_policy = data.aws_iam_policy_document.eks_csi_efs.json

  tags = local.project_tags
}

data "aws_iam_policy_document" "eks_csi_efs" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "eks_csi_efs" {
  role       = aws_iam_role.eks_csi_efs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy"
}
