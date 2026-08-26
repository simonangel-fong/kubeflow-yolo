# locals.tf

data "aws_availability_zones" "available" {
  state = "available"
}

# Long-lived resources owned by ../project.
data "terraform_remote_state" "project" {
  backend = "s3"

  config = {
    bucket = var.project_state_bucket
    key    = var.project_state_key
    region = var.aws_region
  }
}

locals {
  # ##############################
  # Metadata
  # ##############################
  project_name   = "kubeflow-yolo"
  project_prefix = "${local.project_name}-${var.env}"
  project_tags = {
    Name      = local.project_prefix
    Project   = local.project_name
    Env       = var.env
    ManagedBy = "Terraform"
  }

  # ##############################
  # Project resources (remote state)
  # ##############################
  s3_bucket_name = data.terraform_remote_state.project.outputs.s3_bucket_name
  s3_bucket_arn  = data.terraform_remote_state.project.outputs.s3_bucket_arn

  # ##############################
  # AWS
  # ##############################
  aws_azs = slice(data.aws_availability_zones.available.names, 0, 3)

  # ##############################
  # VPC
  # ##############################
  vpc_cidr = "10.0.0.0/16"
  vpc_public_subnets = {
    for i, az in local.aws_azs : az => cidrsubnet(local.vpc_cidr, 8, i + 100)
  }

  vpc_private_subnets = {
    for i, az in local.aws_azs : az => cidrsubnet(local.vpc_cidr, 8, i + 10)
  }

  # ##############################
  # EKS
  # ##############################
  eks_version = "1.36"

  eks_node_instance_type = "t3.large"
  eks_node_count_desired = 2
  eks_node_count_min     = 2
  eks_node_count_max     = 5
  eks_node_disk_size     = 50

  # controllerManager and scheduler are high-volume and rarely read, so they
  # stay off; audit is the stream that answers "who changed this?".
  eks_enabled_log_types  = ["api", "audit", "authenticator"]
  eks_log_retention_days = 30

  # ##############################
  # Karpenter
  # ##############################
  karpenter_namespace     = "kube-system"
  karpenter_chart_version = "1.14.0"
  karpenter_discovery     = local.project_prefix

  # ##############################
  # ArgoCD
  # ##############################
  argocd_release       = "argocd"
  argocd_chart         = "argo-cd"
  argocd_repo          = "https://argoproj.github.io/argo-helm"
  argocd_chart_version = "10.4.0"
  argocd_namespace     = "argocd"

  argocd_values = yamlencode({
    global = {
      # schdule argocd only to node with taint
      tolerations = [
        {
          key      = "workload-class"
          operator = "Equal"
          value    = "platform"
          effect   = "NoSchedule"
        },
      ]
    }
    server = {
      service = {
        type = "ClusterIP"
      }
      extensions = {
        enabled = true
        contents = [
          {
            name = "rollout-extension"
            url  = "https://github.com/argoproj-labs/rollout-extension/releases/download/v0.3.7/extension.tar"
          }
        ]
      }
    }
  })

  # ##############################
  # ESO
  # ##############################
  eso_namespace       = "external-secrets"
  eso_service_account = "external-secrets"

  # ##############################
  # AWS Load Balancer Controller
  # ##############################
  albc_namespace       = "kube-system"
  albc_service_account = "aws-load-balancer-controller"

  # ##############################
  # Kubeflow
  # ##############################
  kubeflow_profile_namespace       = "kubeflow-yolo"
  kubeflow_profile_service_account = "default-editor"

  # ##############################
  # MLflow
  # ##############################
  mlflow_namespace       = "kubeflow"
  mlflow_service_account = "mlflow"
  mlflow_s3_prefix       = "mlflow/"

  # ##############################
  # Monitoring
  # ##############################
  # The kube-prometheus-stack itself is an ArgoCD Application
  # (argocd/init/monitoring.yaml); Terraform only owns the Grafana credential.
  monitoring_namespace = "monitoring"
}
