# argocd.tf

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = local.argocd_chart_version

  namespace        = local.argocd_namespace
  create_namespace = true

  # CRDs must land before the root Application is applied.
  wait          = true
  wait_for_jobs = true
  timeout       = 900

  values = [yamlencode({
    # Terraform installs ArgoCD only; the app-of-apps in argocd/ owns everything
    # else. Keep workload config in git, not here.
    server = {
      service = {
        type = "ClusterIP"
      }
    }
  })]

  depends_on = [module.eks]
}
