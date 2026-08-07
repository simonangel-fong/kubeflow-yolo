# AGENTS.md

## Project

Train a YOLO model to detect vehicle plate positions in images, then deploy and
serve it on AWS.

- Current plan and stage: [docs/PLAN.md](docs/PLAN.md) — changes as the project progresses, read it first.
- Prior work: https://github.com/simonangel-fong/VehiclePlateDetector.git

## Layout

```txt
├── .github/                  # CI/CD pipelines (GitHub Actions workflows)
├── configs/                  # Model hyperparameters and environment config
├── data/
│   ├── raw/                  # Immutable, untouched source datasets
│   └── processed/            # Finalized arrays used directly for training
├── docs/                     # Documentation, architecture, API specs
├── models/                   # Serialized artifacts, weights, checkpoints
├── notebooks/                # EDA and prototyping
├── src/                      # Core production source code
│   ├── data_loader.py        # Data loading, pipelines, preprocessing
│   ├── train.py              # Training entry point
│   ├── inference.py          # Local running / prediction serving
│   ├── models.py             # Network architecture and model classes
│   └── utils.py              # Logging, custom metrics, shared helpers
├── tests/                    # Unit, integration, validation tests
└── requirements.txt          # Python dependencies
```

Target layout — create directories when needed, not ahead of time.

## Rules

- MUST NOT run `git push` or `terraform apply`. Ask the user; they run it.

## Conventions

- Python, YOLO (Ultralytics), Kubeflow for orchestration, AWS for serving.
- Never commit datasets, weights, or checkpoints. `.gitignore` blocks `data/`
  and `models/` contents deliberately.
- Notebooks are for exploration; anything reused belongs in `src/` as a function.
- Hyperparameters live in `configs/`, not hardcoded in scripts.
- Windows 11 / PowerShell environment.

## Responses

Be concise and clear. No preamble, no restating the request, no summary of
changes already visible in the diff.
