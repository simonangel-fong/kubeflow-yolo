# vpc.tf

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = "${local.project_prefix}-vpc"
  cidr = local.vpc_cidr

  azs             = keys(local.vpc_public_subnets)
  public_subnets  = values(local.vpc_public_subnets)
  private_subnets = values(local.vpc_private_subnets)

  # Single NAT gateway keeps dev cost down; private subnets still reach the internet.
  enable_nat_gateway = true
  single_nat_gateway = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  # Required by EKS to discover subnets for load balancers.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = local.project_tags
}
