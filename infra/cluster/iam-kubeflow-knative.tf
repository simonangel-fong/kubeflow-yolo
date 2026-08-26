# iam-kubeflow-knative.tf

# ##############################
# IAM role: kubeflow Knative
# ##############################
resource "aws_iam_role" "kubeflow_knative" {
  name               = "${local.project_prefix}-kubeflow-knative"
  assume_role_policy = data.aws_iam_policy_document.kubeflow_knative_assume_role.json
}

data "aws_iam_policy_document" "kubeflow_knative_assume_role" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_eks_pod_identity_association" "kubeflow_knative" {
  cluster_name    = module.eks.cluster_name
  namespace       = local.knative_namespace
  service_account = local.knative_service_account
  role_arn        = aws_iam_role.kubeflow_knative.arn
}

resource "aws_iam_role_policy_attachment" "kubeflow_knative_ecr_read" {
  role       = aws_iam_role.kubeflow_knative.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}