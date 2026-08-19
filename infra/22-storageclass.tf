# storageclass.tf
#
# The EBS CSI addon installs the driver but no StorageClass; EKS ships a legacy
# in-tree `gp2` class as default. Make gp3 the default instead.

resource "kubernetes_annotations" "gp2_not_default" {
  api_version = "storage.k8s.io/v1"
  kind        = "StorageClass"
  force       = true

  metadata {
    name = "gp2"
  }

  annotations = {
    "storageclass.kubernetes.io/is-default-class" = "false"
  }

  depends_on = [module.eks]
}

resource "kubernetes_storage_class_v1" "gp3" {
  metadata {
    name = "gp3"

    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }

  storage_provisioner = "ebs.csi.aws.com"
  # WaitForFirstConsumer: EBS volumes are AZ-bound, so binding must wait until
  # the scheduler picks a node, otherwise the volume can land in the wrong AZ.
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  reclaim_policy         = "Delete"

  parameters = {
    type      = "gp3"
    encrypted = "true"
    fsType    = "ext4"
  }

  depends_on = [kubernetes_annotations.gp2_not_default]
}
