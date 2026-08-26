# # eks-efs.tf
# #
# # Shared ReadWriteMany storage for the dataset. EBS is ReadWriteOnce and binds
# # to a single node, so parallel Katib trials on separate nodes cannot share it;
# # EFS can be mounted read-only by every trial at once.

# # ##############################
# # Security group
# # ##############################
# # NFS from the node security group only; the filesystem is never public.
# resource "aws_security_group" "efs" {
#   name        = "${local.project_prefix}-efs"
#   description = "NFS access to the shared dataset filesystem"
#   vpc_id      = module.vpc.vpc_id

#   tags = merge(local.project_tags, { Name = "${local.project_prefix}-efs" })
# }

# resource "aws_vpc_security_group_ingress_rule" "efs_nfs_from_nodes" {
#   security_group_id = aws_security_group.efs.id
#   description       = "NFS from EKS nodes"

#   ip_protocol                  = "tcp"
#   from_port                    = 2049
#   to_port                      = 2049
#   referenced_security_group_id = module.eks.node_security_group_id
# }

# # ##############################
# # Filesystem
# # ##############################
# # Elastic throughput: the access pattern is bursty (a populate job, then reads
# # at trial startup), so provisioned throughput would be paid for while idle.
# resource "aws_efs_file_system" "data" {
#   creation_token = "${local.project_prefix}-data"
#   encrypted      = true

#   performance_mode = "generalPurpose"
#   throughput_mode  = "elastic"

#   tags = merge(local.project_tags, { Name = "${local.project_prefix}-data" })
# }

# # One mount target per private subnet: a pod can only mount from an ENI in its
# # own AZ, and Karpenter may place GPU nodes in any of them.
# resource "aws_efs_mount_target" "data" {
#   for_each = toset(module.vpc.private_subnets)

#   file_system_id  = aws_efs_file_system.data.id
#   subnet_id       = each.value
#   security_groups = [aws_security_group.efs.id]
# }

# # ##############################
# # IAM for the EFS CSI driver addon
# # ##############################
# data "aws_iam_policy_document" "efs_csi_assume_role" {
#   statement {
#     effect  = "Allow"
#     actions = ["sts:AssumeRole", "sts:TagSession"]

#     principals {
#       type        = "Service"
#       identifiers = ["pods.eks.amazonaws.com"]
#     }
#   }
# }

# resource "aws_iam_role" "efs_csi" {
#   name               = "${local.project_prefix}-efs-csi"
#   assume_role_policy = data.aws_iam_policy_document.efs_csi_assume_role.json

#   tags = local.project_tags
# }

# resource "aws_iam_role_policy_attachment" "efs_csi" {
#   role       = aws_iam_role.efs_csi.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy"
# }
