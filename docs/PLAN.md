## Stage 1 — Local train

Train a YOLO model locally to detect license plates, in a notebook, referencing
the prior lab (VehiclePlateDetector).

**Goal is the training pipeline, not model accuracy.** Prefer a small subset and
few epochs over a long run.

---

## Stack

- Python 3.12, venv
- Ultralytics YOLO (latest), pretrained `yolo11n.pt`
- Jupyter (local kernel)

---

## Starting point

- `data/` holds **556 image + label pairs** (flat, already downloaded) plus
  `classes.txt`.
- Labels are YOLO format, **single class `0` = license plate**. Some images have
  multiple boxes.
- Images are mixed `.jpeg` / `.png`; filenames contain spaces.

---

## Phases

| #   | Phase               | Description                                | Done when                                         | Status |
| --- | ------------------- | ------------------------------------------ | ------------------------------------------------- | ------ |
| 0   | Fix `.gitignore`    | Stop git tracking datasets and weights     | `git status` shows no dataset files               | done   |
| 1   | Download image data | Download data from archived Google Drive   | Images + labels present in `data/raw/`            | done   |
| 2   | Setup venv          | venv, `requirements.txt`, install packages | `import ultralytics` works in the notebook kernel |        |
| 3   | Create notebook     | Notebook wired to the venv kernel          | Kernel runs a cell                                |        |
| 4   | Configure model     | Prepare data, then configure the model     | `YOLO` loads the dataset without error            |        |
| 5   | Train model         | Train                                      | Run completes, weights written                    |        |
| 6   | Test and evaluate   | Test, validate                             | Metrics printed, predictions plausible            |        |

### Notes

- Phase 3 is the real risk. Data prep lives here — the split into the
  `images/`/`labels/` layout, and the `data.yaml` describing it. YOLO fails
  quietly on a mismatched layout, so verify pairing before training.
- Reusable logic (split, pairing check) → `src/`, not the notebook.

---

## Optional (after Phase 6 works end to end)

| #   | Phase                 | Description                     |
| --- | --------------------- | ------------------------------- |
| A   | Setup MLflow          | MLflow via Docker               |
| B   | Track training        | Log params/metrics from the run |
| C   | Hyperparameter tuning | Sweep with MLflow tracking      |

---

## Output

`docs/01-local-train.md` — write-up of the stage (currently empty).
