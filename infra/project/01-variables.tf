# variables.tf

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
# Cloudflare
# ##############################
variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone:DNS:Edit on the website zone"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone hosting the website record"
  type        = string
}
