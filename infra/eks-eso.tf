# eks-eso.tf

# ##############################
# Secrets: cloudflare-api-token
# ##############################
resource "aws_secretsmanager_secret" "eso_cloudflare" {
  count = var.enable_eks ? 1 : 0

  name = "${module.eks[0].cluster_name}/cloudflare-api-token"
}

resource "aws_secretsmanager_secret_version" "eso_cloudflare" {
  count = var.enable_eks ? 1 : 0

  secret_id     = aws_secretsmanager_secret.eso_cloudflare[0].id
  secret_string = jsonencode({ apiToken = var.eso_cloudflare_api_token })
}
