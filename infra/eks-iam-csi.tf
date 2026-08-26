# eks-iam-csi.tf

# ##############################
# IAM: allow EBS CSI driver addon
# ##############################
data "aws_iam_policy_document" "eks_csi_ebs" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_csi_ebs" {
  name               = "${local.project_prefix}-csi-ebs"
  assume_role_policy = data.aws_iam_policy_document.eks_csi_ebs.json

  tags = local.project_tags
}

resource "aws_iam_role_policy_attachment" "eks_csi_ebs" {
  role       = aws_iam_role.eks_csi_ebs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}