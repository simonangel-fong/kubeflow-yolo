# argocd.tf

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = local.argocd_chart_version

  namespace        = local.argocd_namespace
  create_namespace = true

  wait          = true
  wait_for_jobs = true
  timeout       = 900

  values = [yamlencode({
    server = {
      service = {
        type = "ClusterIP"
      }
    }
  })]

  depends_on = [module.eks]
}
