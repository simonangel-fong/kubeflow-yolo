# eks-eso.tf

# ##############################
# Secrets: cloudflare-api-token
# ##############################
resource "aws_secretsmanager_secret" "eso_cloudflare" {
  name = "${module.eks.cluster_name}/cloudflare-api-token"
}

resource "aws_secretsmanager_secret_version" "eso_cloudflare" {
  secret_id     = aws_secretsmanager_secret.eso_cloudflare.id
  secret_string = jsonencode({ apiToken = var.eso_cloudflare_api_token })
}






# # ##############################
# # Secret: mlflow postgres credentials
# # ##############################
# resource "random_password" "mlflow_postgres" {
#   length  = 32
#   special = false
# }

# resource "aws_secretsmanager_secret" "mlflow_postgres" {
#   name = "${module.eks.cluster_name}/mlflow-postgres"
# }

# resource "aws_secretsmanager_secret_version" "mlflow_postgres" {
#   secret_id = aws_secretsmanager_secret.mlflow_postgres.id
#   secret_string = jsonencode({
#     username = "mlflow"
#     password = random_password.mlflow_postgres.result
#   })
# }

# # ##############################
# # Secret: mlflow flask session key
# # ##############################
# # The chart generates this at render time when unset, which means a new key on
# # every Argo sync (invalidating sessions). Pin it here and deliver via ESO.
# resource "random_password" "mlflow_flask_key" {
#   length  = 64
#   special = false
# }

# resource "aws_secretsmanager_secret" "mlflow_flask_key" {
#   name = "${module.eks.cluster_name}/mlflow-flask-key"
# }

# resource "aws_secretsmanager_secret_version" "mlflow_flask_key" {
#   secret_id     = aws_secretsmanager_secret.mlflow_flask_key.id
#   secret_string = jsonencode({ key = random_password.mlflow_flask_key.result })
# }
