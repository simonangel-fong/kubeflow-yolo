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
variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone:Read + DNS:Edit on the domain_name zone. Set via TF_VAR_cloudflare_api_token or tfvars."
  type        = string
  sensitive   = true
}

# ##############################
# EKS
# ##############################
variable "enable_eks" {
  description = "flag to control whether to enable eks cluster"
  default     = false
}
