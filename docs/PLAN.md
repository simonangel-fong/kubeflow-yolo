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

| #   | Phase                            | Description                                                                                       | Done when                                         |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 0   | Fix `.gitignore`                 | Add `data/*` and `models/*` — the current file does **not** ignore them                           | `git status` shows no dataset files               |
| 1   | Restructure data                 | Move flat `data/` → `data/raw/`; script a split into `data/processed/{train,val}/{images,labels}` | Every image has a matching label; no orphans      |
| 2   | `data.yaml`                      | Path, `nc: 1`, `names: [license_plate]` in `configs/`                                             | `YOLO` loads it without error                     |
| 3   | Setup venv                       | `.venv`, `requirements.txt` (ultralytics, jupyter, ipykernel)                                     | `import ultralytics` works in the notebook kernel |
| 4   | `notebooks/01-local-train.ipynb` | Notebook wired to the venv kernel                                                                 | Kernel runs a cell                                |
| 5   | Configure + train                | Load `yolo11n.pt`, small `imgsz`/`epochs`, CPU-safe; log device used                              | Run completes, weights in `runs/`                 |
| 6   | Evaluate                         | `model.val()` → mAP50; predict on a few val images and view boxes                                 | Metrics printed, predictions visually plausible   |

### Notes

- Phase 1 is the real risk: verify pairing and the split **before** training —
  YOLO fails quietly on a mismatched `images/`/`labels/` layout.
- Consider renaming files to strip spaces during the split.
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
