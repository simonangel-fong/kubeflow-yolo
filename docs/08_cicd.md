# CI/CD: GitHub Actions

[Back](../README.md)

- [CI/CD: GitHub Actions](#cicd-github-actions)
  - [Prerequisites](#prerequisites)
  - [`build-image-train` pipeline](#build-image-train-pipeline)
  - [`build-image-kserve` pipeline](#build-image-kserve-pipeline)
  - [`build-image-frontend` pipeline](#build-image-frontend-pipeline)
  - [`terraform-apply` pipeline](#terraform-apply-pipeline)

---

## Prerequisites

enable OIDC in infra/
config github var, secret, and env

- repo var

  | varible             | default values                                                               |
  | ------------------- | ---------------------------------------------------------------------------- |
  | `AWS_REGION`        | ca-central-1                                                                 |
  | `AWS_OIDC_ROLE_ARN` | `terraform -chdir=infra/project output -raw github_actions_role_arn`         |
  | `ECR_REPO_TRAIN`    | `terraform -chdir=infra/project output ecr_repository_urls`                  |
  | `ECR_REPO_KSERVE`   | `terraform -chdir=infra/project output ecr_repository_urls`                  |
  | `ECR_REPO_FRONTEND` | `terraform -chdir=infra/project output ecr_repository_urls`                  |
  | `TF_PLAN_ROLE_ARN`  | `terraform -chdir=infra/project output -raw github_terraform_plan_role_arn`  |
  | `TF_APPLY_ROLE_ARN` | `terraform -chdir=infra/project output -raw github_terraform_apply_role_arn` |

- env var: `tf-apply`

  | varible | default values |
  | ------- | -------------- |
  | `ENV`   | dev            |

```sh
gh variable set ENV --body "dev" --env "tf-apply"
# ✓ Created variable ENV for simonangel-fong/kubeflow-yolo environment tf-apply

gh variable set AWS_REGION --body "ca-central-1"
# ✓ Created variable AWS_REGION for simonangel-fong/kubeflow-yolo

terraform -chdir=infra/project output -raw github_actions_role_arn
gh variable set AWS_OIDC_ROLE_ARN --body "arn:aws:iam::099139718958:role/kubeflow-yolo-dev-github-ecr-push"
# ✓ Set Actions secret AWS_OIDC_ROLE_ARN for simonangel-fong/kubeflow-yolo

terraform -chdir=infra/project output ecr_repository_urls
gh variable set ECR_REPO_TRAIN --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-train"
# ✓ Created variable ECR_REPO_TRAIN for simonangel-fong/kubeflow-yolo

gh variable set ECR_REPO_KSERVE --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve"
# ✓ Created variable ECR_REPO_KSERVE for simonangel-fong/kubeflow-yolo

gh variable set ECR_REPO_FRONTEND --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-frontend"
# ✓ Created variable ECR_REPO_FRONTEND for simonangel-fong/kubeflow-yolo

terraform -chdir=infra/project output -raw github_terraform_plan_role_arn
gh variable set TF_PLAN_ROLE_ARN --body "arn:aws:iam::099139718958:role/kubeflow-yolo-dev-github-terraform-plan"
# ✓ Created variable TF_PLAN_ROLE_ARN for simonangel-fong/kubeflow-yolo

terraform -chdir=infra/project output -raw github_terraform_apply_role_arn
gh variable set TF_APPLY_ROLE_ARN --body "arn:aws:iam::099139718958:role/kubeflow-yolo-dev-github-terraform-apply"
# ✓ Updated variable TF_APPLY_ROLE_ARN for simonangel-fong/kubeflow-yolo

# gate apply behind required reviewers before the first run
gh api -X PUT repos/simonangel-fong/kubeflow-yolo/environments/tf-apply -F "reviewers[][type]=User" -F "reviewers[][id]=64545430"

gh secret set CLOUDFLARE_API_TOKEN --body "<api_token>"
# ✓ Set Actions secret CLOUDFLARE_API_TOKEN for simonangel-fong/kubeflow-yolo
gh secret set CLOUDFLARE_ZONE_ID --body "<zone_id>"
```

---

## `build-image-train` pipeline

Automate training image build and push job.

- Trigger:
  - train-job/\*\*
  - manual

| Core Steps              | Description                 |
| ----------------------- | --------------------------- |
| checkout                | Clone the repo;             |
| get aws access via oidc | configure AWS credentials   |
| login aws ecr           | Login AWS ECR               |
| setup buildx            | BuildKit driver             |
| build and push          | build docker image and push |

```sh
# confirm
aws ecr list-images --repository-name kubeflow-yolo-train --region ca-central-1
```

---

## `build-image-kserve` pipeline

Automate kserve image build and push job.

- Trigger:
  - inference/\*\*
  - manual

| Core Steps              | Description                 |
| ----------------------- | --------------------------- |
| checkout                | Clone the repo;             |
| get aws access via oidc | configure AWS credentials   |
| login aws ecr           | Login AWS ECR               |
| setup buildx            | BuildKit driver             |
| build and push          | build docker image and push |

```sh
# confirm
aws ecr list-images --repository-name kubeflow-yolo-kserve --region ca-central-1
```

---

## `build-image-frontend` pipeline

Automate frontend image build and push job.

- Trigger:
  - frontend/\*\*
  - manual

| Core Steps              | Description                 |
| ----------------------- | --------------------------- |
| checkout                | Clone the repo;             |
| get aws access via oidc | configure AWS credentials   |
| login aws ecr           | Login AWS ECR               |
| setup buildx            | BuildKit driver             |
| build and push          | build docker image and push |

```sh
# confirm
aws ecr list-images --repository-name kubeflow-yolo-frontend --region ca-central-1
```

---

## `terraform-apply` pipeline

Plan and apply `infra/`. Split in two, because apply needs near-admin AWS
rights and this is a public repo.

- Trigger:
  - PR / push touching infra/\*\* -> **plan** (read-only role)
  - manual dispatch `action=apply` -> **apply** (admin role, gated)

| Core Steps              | Description                                                                |
| ----------------------- | -------------------------------------------------------------------------- |
| setup terraform         | setup terraform                                                            |
| get aws access via oidc | get aws access                                                             |
| init                    | initialize terraform                                                       |
| fmt / validate          | check format and validate                                                  |
| plan                    | Create plan                                                                |
| apply                   | Manual only; plans and applies in the same job to avoid a stale saved plan |

- Roles:

| Role                                       | Rights                              | Trust condition                  |
| ------------------------------------------ | ----------------------------------- | -------------------------------- |
| `kubeflow-yolo-dev-github-terraform-plan`  | `ReadOnlyAccess` + state bucket R/W | any ref on this repo             |
| `kubeflow-yolo-dev-github-terraform-apply` | `AdministratorAccess`               | `:environment:tf-apply` **only** |

```sh
# plan runs automatically on a PR touching infra/; to apply:
gh workflow run terraform-apply.yml -f action=apply
```
