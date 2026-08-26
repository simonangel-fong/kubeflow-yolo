# variables.tf
#
# The cluster is enabled/disabled by applying or destroying this root module,
# not by a flag: `terraform destroy` here is the off-switch. Long-lived
# resources (S3, ECR, OIDC) live in ../project and are unaffected.

# ##############################
# Metadata
# ##############################
variable "env" {
  description = "Environment"
  type        = string
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
  description = "AWS region"
  type        = string
}

# ##############################
# ESO
# ##############################
variable "eso_cloudflare_api_token" {
  description = "ESO Cloudflare API token."
  type        = string
  sensitive   = true
}

# ##############################
# Remote state: project
# ##############################
variable "project_state_bucket" {
  description = "S3 bucket holding the project root module state"
  type        = string
}

variable "project_state_key" {
  description = "Key of the project root module state object"
  type        = string
}
