# CI/CD: GitHub Actions

[Back](../README.md)

- [CI/CD: GitHub Actions](#cicd-github-actions)
  - [Prerequisites](#prerequisites)
  - [`train-image-build` pipeline](#train-image-build-pipeline)
  - [Prerequisites](#prerequisites-1)
  - [Steps](#steps)

---

## Prerequisites

- enable OIDC in infra/
- config github var, secret, and env
  - repo var

  | varible             | default values                                               |
  | ------------------- | ------------------------------------------------------------ |
  | `AWS_REGION`        | ca-central-1                                                 |
  | `AWS_OIDC_ROLE_ARN` | `terraform -chdir=infra output -raw github_actions_role_arn` |
  | `ECR_REPO_TRAIN`    | `terraform -chdir=infra output ecr_repository_urls`          |
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

gh secret set CLOUDFLARE_API_TOKEN --body "<api_token>"
gh secret set CLOUDFLARE_ZONE_ID --body "<zone_id>"
```

---

## `train-image-build` pipeline

Automate training image build and push job.

- Trigger:
  - train-job/\*\*
  - manual

| Core Steps              | Description |
| ----------------------- | ----------- |
| get aws access via oidc |             |
| login aws ecr           |             |
| setup buildx            |             |
| build and push          |             |

---

## Prerequisites

1. [infra/project-github-oidc.tf](../infra/project-github-oidc.tf) — OIDC provider
   - IAM role trusting `repo:simonangel-fong/kubeflow-yolo:*`, with ECR push on
     the project repositories. Done.
2. Repo variables: `AWS_REGION`, `AWS_ROLE_ARN`, `ECR_REPOSITORY`.

---

## Steps

1. ~~Add the OIDC provider + role ARN output.~~ Done — run `terraform -chdir=infra apply`.
2. Set the three repo variables (`AWS_ROLE_ARN` from `terraform output github_actions_role_arn`).
3. ~~Add [.github/workflows/train-image-build.yml](../.github/workflows/train-image-build.yml).~~ Done.
4. Verify: `gh workflow run train-image-build.yml -f image_tag=v0.3.2`, then
   `aws ecr list-images --repository-name kubeflow-yolo-train --region ca-central-1`.

Out of scope: bumping the tag in the Katib manifest; the `frontend` / `kserve`
images (same skeleton, matrix later).
