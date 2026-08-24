# eks-vpc.tf

# ##############################
# VPC
# ##############################
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = local.project_prefix

  cidr            = local.vpc_cidr
  azs             = keys(local.vpc_public_subnets)
  public_subnets  = values(local.vpc_public_subnets)
  private_subnets = values(local.vpc_private_subnets)

  # Enable nat gateway
  enable_nat_gateway = true
  single_nat_gateway = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  # tag: elb
  public_subnet_tags = {
    "kubernetes.io/role/elb"                        = "1"
    "kubernetes.io/cluster/${local.project_prefix}" = "shared"
  }

  # tab: kapenter;
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1" # lb
    "karpenter.sh/discovery"          = local.project_prefix
  }

  tags = local.project_tags
}
