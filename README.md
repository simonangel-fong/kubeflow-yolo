# GPU-Enabled MLOps Platform on `AWS EKS` with `kubeflow`

> One platform. 3 engineerings. End-to-end MLOps practice.

An end-to-end **MLOps platform** that trains, tracks, deploys, and serves a YOLO object detection model on `AWS EKS` using `Kubeflow`, `MLflow`, `KServe`, `Terraform`, `Argo CD`, and `GitHub Actions`.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white) ![Ultralytics YOLO](https://img.shields.io/badge/Ultralytics%20YOLO-111F68?style=flat-square&logo=ultralytics&logoColor=white) ![ONNX](https://img.shields.io/badge/ONNX-005CED?style=flat-square&logo=onnx&logoColor=white) ![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=flat-square&logo=jupyter&logoColor=white) ![Kubeflow](https://img.shields.io/badge/Kubeflow-2C2C32?style=flat-square&logo=kubeflow&logoColor=white) ![MLflow](https://img.shields.io/badge/MLflow-0194E2?style=flat-square&logo=mlflow&logoColor=white) ![KServe](https://img.shields.io/badge/KServe-2C2C32?style=flat-square&logo=kubernetes&logoColor=white) ![DVC](https://img.shields.io/badge/DVC-13ADC7?style=flat-square&logo=dvc&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)

![AWS](https://img.shields.io/badge/AWS-FF9900?style=flat-square&logo=amazonwebservices&logoColor=white) ![Amazon EKS](https://img.shields.io/badge/Amazon%20EKS-FF9900?style=flat-square&logo=amazoneks&logoColor=white) ![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white) ![NVIDIA GPU](https://img.shields.io/badge/NVIDIA%20GPU-76B900?style=flat-square&logo=nvidia&logoColor=white) ![Karpenter](https://img.shields.io/badge/Karpenter-FF9900?style=flat-square&logo=amazonwebservices&logoColor=white) ![Istio](https://img.shields.io/badge/Istio-466BB0?style=flat-square&logo=istio&logoColor=white) ![Helm](https://img.shields.io/badge/Helm-0F1689?style=flat-square&logo=helm&logoColor=white) ![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white) ![Grafana](https://img.shields.io/badge/Grafana-F46800?style=flat-square&logo=grafana&logoColor=white) ![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=flat-square&logo=cloudflare&logoColor=white)

![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=flat-square&logo=terraform&logoColor=white) ![Argo CD](https://img.shields.io/badge/Argo%20CD-EF7B4D?style=flat-square&logo=argo&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white) ![GitHub](https://img.shields.io/badge/GitHub-121011?style=flat-square&logo=github&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![Kustomize](https://img.shields.io/badge/Kustomize-326CE5?style=flat-square&logo=kubernetes&logoColor=white) ![NGINX](https://img.shields.io/badge/NGINX-009639?style=flat-square&logo=nginx&logoColor=white)

- [GPU-Enabled MLOps Platform on `AWS EKS` with `kubeflow`](#gpu-enabled-mlops-platform-on-aws-eks-with-kubeflow)
  - [Business Challenge](#business-challenge)
  - [Architecture](#architecture)
  - [ML Engineering](#ml-engineering)
    - [ML Engineering in Action](#ml-engineering-in-action)
  - [Platform Engineering](#platform-engineering)
    - [Infrastructure as Code](#infrastructure-as-code)
    - [Platform Capabilities](#platform-capabilities)
    - [Platform engineering in Action](#platform-engineering-in-action)
  - [DevOps Engineering](#devops-engineering)
    - [CI/CD Pipelines with `GitHub Actions`](#cicd-pipelines-with-github-actions)
    - [GitOps with `Argo CD`](#gitops-with-argo-cd)
  - [Roadmap](#roadmap)
  - [Documentation](#documentation)

---

## Business Challenge

**Machine learning models** can deliver strong business value, but moving them from **experimentation** to reliable **production** use requires more than model training.

> THow do teams close the **GAP** between <u>experimentation</u> and <u>production</u>?

This project addresses that challenge building an end-to-end MLOps platform for a YOLO object detection model with **3 engineering perspectives**:

1. `ML Engineering`: experiment, train, track, store, and serve the model.
2. `Platform Engineering`: provide scalable `GPU` compute, storage, networking, security, and observability on `EKS`.
3. `DevOps Engineering`: automate infrastructure and application delivery with `Terraform`, `GitHub Actions`, `Argo CD`, and `GitOps`.

---

- **Live application demo**: car plate detection

![app_demo01](./docs/img/app_demo01.png)

---

## Architecture

- Architecture Diagram

![diagram_architecture](./docs/img/diagram_architecture.gif)

- Repository Layout

```text
kubeflow-yolo/
├── .github/
│   └── workflows/          # CI/CD workflows
├── data/                   # Dataset files and related assets
├── argocd/                 # Argo CD applications and platform components
├── app-of-apps.yaml        # Argo CD root application
├── infra/                  # Terraform modules and AWS infrastructure
├── jupyter-notebook/       # Model development and experimentation notebooks
├── kubeflow/               # Kubeflow pipelines and related configurations
├── train-job/              # YOLO training code and training image
├── inference/              # KServe inference application and image
├── frontend/               # Web UI and Nginx image
├── docs/                   # Detailed implementation documentation
└── README.md               # Project overview and documentation index
```

---

## ML Engineering

![diagram_mlops](./docs/img/diagram_mlops.gif)

| #   | ML Stage          | Components / Technologies                                                                                      |
| --- | ----------------- | -------------------------------------------------------------------------------------------------------------- |
| 1   | Data preparation  | Images and labels stored in `S3`; versioned with `DVC`                                                         |
| 2   | Model development | `Jupyter Notebook`                                                                                             |
| 3   | Experimentation   | `Katib` for hyperparameter trials; `MLflow` for metrics and run tracking                                       |
| 4   | Training pipeline | `Kubeflow Pipeline` for orchestration; artifacts stored in `S3`; model registered and versioned after training |
| 5   | Model serving     | `KServe` for online inference                                                                                  |

---

### ML Engineering in Action

- **Data**: images and labels
  ![data_images](./docs/img/data_images.png)

- **Development**: model exploration in `Jupyter`
  ![kf_notebook_train01](./docs/img/kf_notebook_train01.png)

- **Experiments**: `Katib` runs trials
  ![mlops_katib](./docs/img/kf_katib01.png)

- **Experiments**: `MLflow` tracks metrics
  ![mlflow_metrics02](./docs/img/mlflow_metrics02.png)

- **Pipeline**: `Kubeflow Pipeline` trains, evaluates, and registers
  ![kf_pipeline02](./docs/img/kf_pipeline02.png)

- **Serving**: deploy the selected model with `KServe`
  ![kf_kserve_endpoint01](./docs/img/kf_kserve_endpoint01.png)

---

## Platform Engineering

![diagram_platform](./docs/img/diagram_platform.gif)

### Infrastructure as Code

AWS infrastructure is managed with **Terraform**:

- using an **`S3` remote backend**
- integrating `GitHub Actions` for `fmt`, `validate`, `plan`, and `apply`.

---

### Platform Capabilities

| Capability | Infrastructure / Cluster                                     | Purpose                                          |
| ---------- | ------------------------------------------------------------ | ------------------------------------------------ |
| Compute    | EKS, Karpenter, node selectors                               | Autoscaling and GPU node provisioning            |
| Storage    | S3, EBS, EFS, StorageClass, PVC                              | Persistent and shared storage for ML workloads   |
| Networking | VPC, ALBC, Istio, Gateway API, ExternalDNS                   | North-south/east-west traffic and automated DNS  |
| Security   | Secrets Manager, KMS, ESO, cert-manager, NetworkPolicy, mTLS | Secrets, encryption, certificates, and isolation |
| Monitoring | Prometheus, Grafana                                          | Logs and platform metrics                        |

---

### Platform engineering in Action

- EKS cluster

![infra_eks](./docs/img/infra_eks.png)

- Self-managed nodes `GPU` nodes via `Karpenter`

![infra_eks_node_gpu](./docs/img/infra_eks_node_gpu.png)

- Grafana dashboard - GPU

![monitor_grafana01](./docs/img/monioring_gpu01.png)

- Grafana dashboard - Cluster

![monitor_grafana01](./docs/img/monitoring_k8s01.png)

---

## DevOps Engineering

### CI/CD Pipelines with `GitHub Actions`

| Pipeline                | Key Steps                                   | Purpose                                |
| ----------------------- | ------------------------------------------- | -------------------------------------- |
| `terraform-apply`       | Trigger, `fmt`, `validate`, `plan`, `apply` | Deploy infrastructure with `Terraform` |
| `build-image-train`     | Trigger, build, push                        | Publish **training** image to `ECR`    |
| `build-image-inference` | Trigger, build, push                        | Publish **inference** image to `ECR`   |
| `build-image-frontend`  | Trigger, build, push                        | Publish **frontend** image to `ECR`    |

- CI/CD pipeline in action

![cicd_build_train](./docs/img/cicd_build_train.png)

---

### GitOps with `Argo CD`

Use GitOps practices to manage deployment via `Argo CD`:

- **App-of-Apps**: declaratively manages platform and application components.
- **`Git` as source of truth**: `Argo CD` continuously reconciles the cluster with the repository.
- **Automated deployment**: platform and application changes are applied through `GitOps`.

- `Argo CD` in action

![argocd01](./docs/img/infra_argocd01.png)

---

## Roadmap

| Stage                      | Focus                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| **Make it work — current** | Deliver a MVP functional end-to-end MLOps platform                                         |
| **Make it right**          | Add model promotion gates, policy as code, latency monitoring, and CI/CD security scanning |
| **Make it fast**           | Optimize container builds with multi-stage build and enable pipeline caching               |
| **Make it efficient**      | Add FinOps practices and deeper Prometheus/Grafana monitoring                              |

---

## Documentation

Detailed implementation guides:

- [Infrastructure with `Terraform`](./docs/01_infra.md)
- [`Kubeflow` Installation](./docs/02_kubeflow_install.md)
- [Model Development in `Jupyter`](./docs/03_kubeflow_notebook.md)
- [Hyperparameter Experiments with `Katib`](./docs/04_kubeflow_katib.md)
- [Training with `Kubeflow Pipelines`](./docs/05_kubeflow_pipeline.md)
- [Model Serving with `KServe`](./docs/06_kubeflow_kserve.md)
- [Frontend Deployment](./docs/07_app_frontend.md)
- [CI/CD pipelines](./docs/08_cicd.md)
- [Monitoring](./docs/09_monitoring.md)

---

- detail docs
