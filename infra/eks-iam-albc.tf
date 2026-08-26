# eks-albc.tf


# AWS-published policy JSON
data "http" "albc_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.4.1/docs/install/iam_policy.json"
}

# ##############################
# IAM role: ALBC
# ##############################
resource "aws_iam_role" "albc" {
  name = "${local.project_prefix}-albc"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_policy" "albc" {
  name   = "${local.project_prefix}-albc"
  policy = data.http.albc_policy.response_body
}

resource "aws_iam_role_policy_attachment" "albc" {
  role       = aws_iam_role.albc.name
  policy_arn = aws_iam_policy.albc.arn
}

resource "aws_eks_pod_identity_association" "albc" {
  cluster_name    = module.eks[0].cluster_name
  namespace       = local.albc_namespace
  service_account = local.albc_service_account
  role_arn        = aws_iam_role.albc.arn
}
