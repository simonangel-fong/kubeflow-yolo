# CI/CD: GitHub Actions

[Back](../README.md)

- [CI/CD: GitHub Actions](#cicd-github-actions)
  - [Prerequisites](#prerequisites)
  - [`train-image-build` pipeline](#train-image-build-pipeline)
  - [`train-image-kserve` pipeline](#train-image-kserve-pipeline)
  - [`kubeflow-yolo-frontend` pipeline](#kubeflow-yolo-frontend-pipeline)

---

## Prerequisites

enable OIDC in infra/
config github var, secret, and env

- repo var

  | varible             | default values                                               |
  | ------------------- | ------------------------------------------------------------ |
  | `AWS_REGION`        | ca-central-1                                                 |
  | `AWS_OIDC_ROLE_ARN` | `terraform -chdir=infra output -raw github_actions_role_arn` |
  | `ECR_REPO_TRAIN`    | `terraform -chdir=infra output ecr_repository_urls`          |
  | `ECR_REPO_KSERVE`   | `terraform -chdir=infra output ecr_repository_urls`          |
  | `ECR_REPO_FRONTEND` | `terraform -chdir=infra output ecr_repository_urls`          |

- env var: `dev`

  | varible | default values |
  | ------- | -------------- |
  | `ENV`   | dev            |

```sh
gh variable set ENV --body "dev" --env "dev"
# ✓ Created variable ENV for simonangel-fong/kubeflow-yolo environment dev


gh variable set AWS_REGION --body "ca-central-1"
# ✓ Created variable AWS_REGION for simonangel-fong/kubeflow-yolo

terraform -chdir=infra output -raw github_actions_role_arn
gh variable set AWS_OIDC_ROLE_ARN --body "arn:aws:iam::099139718958:role/kubeflow-yolo-dev-github-actions"
# ✓ Set Actions secret AWS_OIDC_ROLE_ARN for simonangel-fong/kubeflow-yolo

terraform -chdir=infra output ecr_repository_urls
gh variable set ECR_REPO_TRAIN --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-train"
# ✓ Created variable ECR_REPO_TRAIN for simonangel-fong/kubeflow-yolo

gh variable set ECR_REPO_KSERVE --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-kserve"
# ✓ Created variable ECR_REPO_KSERVE for simonangel-fong/kubeflow-yolo

gh variable set ECR_REPO_FRONTEND --body "099139718958.dkr.ecr.ca-central-1.amazonaws.com/kubeflow-yolo-frontend"
# ✓ Created variable ECR_REPO_FRONTEND for simonangel-fong/kubeflow-yolo

gh secret set CLOUDFLARE_API_TOKEN --body "<api_token>"
gh secret set CLOUDFLARE_ZONE_ID --body "<zone_id>"
```

---

## `train-image-build` pipeline

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

## `train-image-kserve` pipeline

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

## `kubeflow-yolo-frontend` pipeline

Automate frontend image build and push job.

- Trigger:
  - frontend/app/\*\*, frontend/Dockerfile
  - manual

| Core Steps              | Description                                                                                   |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| checkout                | Clone the repo; the build context is the repo root, not `frontend/`                           |
| resolve image tag       | `v<run_number>-<short-sha>`, or the dispatch input; validated before use                      |
| get aws access via oidc | Assume `AWS_OIDC_ROLE_ARN` — short-lived keys, no stored AWS secrets. Needs `id-token: write` |
| login aws ecr           | Docker credential helper for the registry                                                     |
| setup buildx            | BuildKit driver, required for the GHA layer cache                                             |
| build and push          | `frontend/Dockerfile`, `linux/amd64`, tagged `<tag>` + `sha-<short-sha>`, cached `type=gha`   |
| summary                 | Write the pushed image URI to the run summary, to update in the Deployment                    |

- Notes:
  - Path filter is scoped to `frontend/app/` and the Dockerfile: everything the
    image actually contains. `frontend/manifests/` is deployed by ArgoCD, so a
    manifest edit should not rebuild the image.
  - Rollout is not automated — bump the tag in
    [deployment.yaml](../frontend/manifests/deployment.yaml) and let ArgoCD sync.

```sh
# confirm
aws ecr list-images --repository-name kubeflow-yolo-frontend --region ca-central-1
```
