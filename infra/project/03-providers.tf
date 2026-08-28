# providers.tf

terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.58.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.project_tags
  }
}

data "aws_caller_identity" "current" {}

# ACM certificates issued in us-east-1,
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.project_tags
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
