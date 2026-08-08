# AGENTS.md

## Project

Train a YOLO model to detect vehicle plate positions in images, then deploy and
serve it on AWS.

- Current plan and stage: [docs/PLAN.md](docs/PLAN.md) — changes as the project progresses, read it first.
- Full roadmap: [docs/stage.md](docs/stage.md) — all stages, local venv through EKS serving.
- Per-stage write-ups: `docs/NN-<stage>.md`, e.g. [docs/01-local-train.md](docs/01-local-train.md).
- Prior work: https://github.com/simonangel-fong/VehiclePlateDetector.git

## Layout

```txt
├── .github/                  # CI/CD pipelines (GitHub Actions workflows)
├── configs/                  # Model hyperparameters and environment config
│   ├── train.yaml            # Hyperparameters
│   └── data.yaml.example     # Dataset descriptor; data.yaml is generated, untracked
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
- Never commit datasets, weights, or checkpoints. `.gitignore` blocks `data/*`,
  `models/*`, `runs/`, and `*.pt` deliberately.
- Notebooks are for exploration; anything reused belongs in `src/` as a function.
- Hyperparameters live in `configs/`, not hardcoded in scripts.
- Anything holding an absolute local path is generated and untracked, with a
  committed `.example` alongside it.
- Windows 11 / PowerShell environment.

## Gotchas

- `configs/data.yaml` `path` must be **absolute**. Ultralytics resolves a
  relative dataset root against the process cwd, then its own `DATASETS_DIR` —
  never against the yaml's own location. The notebook runs from `notebooks/`.
- Ultralytics downloads `*.pt` weights into the current working directory, so
  they land wherever the notebook was launched from.
- `workers` is inert on Windows (`Using 0 dataloader workers`); it takes effect
  on Linux.
- Training is not reproducible run to run despite `seed`, due to CPU thread
  scheduling.

## Responses

Be concise and clear. No preamble, no restating the request, no summary of
changes already visible in the diff.
