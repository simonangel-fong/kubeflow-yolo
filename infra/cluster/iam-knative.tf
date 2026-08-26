# iam-knative.tf

# ##############################
# IAM role: Knative Serving controller
# ##############################
resource "aws_iam_role" "knative_controller" {
  name               = "${local.project_prefix}-knative-controller"
  assume_role_policy = data.aws_iam_policy_document.knative_controller_assume_role.json
}

data "aws_iam_policy_document" "knative_controller_assume_role" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "knative_controller_ecr_read" {
  role       = aws_iam_role.knative_controller.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_pod_identity_association" "knative_controller" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.knative_namespace
  service_account = local.knative_service_account
  role_arn        = aws_iam_role.knative_controller.arn
}
