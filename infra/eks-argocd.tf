# eks-argocd.tf

resource "helm_release" "argocd" {
  count = var.enable_eks ? 1 : 0

  name       = local.argocd_release
  repository = local.argocd_repo
  chart      = local.argocd_chart
  version    = local.argocd_chart_version

  namespace        = local.argocd_namespace
  create_namespace = true

  wait          = true
  wait_for_jobs = true
  timeout       = 900

  values = [local.argocd_values]

  depends_on = [module.eks]
}
