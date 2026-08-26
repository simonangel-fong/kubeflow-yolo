# eks-efs.tf

# ##############################
# Security group
# ##############################
resource "aws_security_group" "efs" {
  name        = "${local.project_prefix}-efs"
  description = "NFS access to the shared dataset filesystem"
  vpc_id      = module.vpc[0].vpc_id

  tags = merge(local.project_tags, { Name = "${local.project_prefix}-efs" })
}

# allow 2049 port
resource "aws_vpc_security_group_ingress_rule" "efs_nfs_from_nodes" {
  security_group_id = aws_security_group.efs.id
  description       = "NFS from EKS nodes"

  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
  referenced_security_group_id = module.eks[0].node_security_group_id
}

# ##############################
# EFS
# ##############################
resource "aws_efs_file_system" "data" {
  count = var.enable_eks ? 1 : 0

  creation_token = "${local.project_prefix}-data"
  encrypted      = true

  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  tags = merge(local.project_tags, { Name = "${local.project_prefix}-data" })
}

resource "aws_efs_mount_target" "data" {
  for_each = toset(module.vpc[0].private_subnets)

  file_system_id  = aws_efs_file_system.data[0].id
  subnet_id       = each.value
  security_groups = [aws_security_group.efs.id]
}
