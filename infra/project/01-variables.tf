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
