# variables.tf

# ##############################
# Metadata
# ##############################
variable "env" {
  description = "Environmet"
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
  description = "AWS region"
}

# ##############################
# Providers: cloudflare
# ##############################
variable "eso_cloudflare_api_token" {
  description = "ESO Cloudflare API token."
  type        = string
  sensitive   = true
}

# ##############################
# EKS
# ##############################
variable "enable_eks" {
  description = "flag to control whether to enable eks cluster"
  default     = true
}
