# Stage 1 — Local Train

---

### Setup venv

Create the environment and install:

```sh
py -3.12 -m venv .venv

pip install --upgrade pip
pip install -r requirements.txt
```

---

### Configure model

**`configs/data.yaml`**: indicate working dir
**`configs/train.yaml`**: Hyperparameters

**Model**:

- `yolo11n.pt`: the smallest variant, pretrained.

---

### Train model

`model.train(data=data_yaml, **train_cfg)` in the notebook. `project` is made
absolute — it is otherwise relative to the working directory, which puts output
in `notebooks/runs/`.

10 epochs, 445 train / 111 val images, `imgsz=416`, `batch=8`, CPU:

```text
elapsed: 1031s
```

| Metric   | Value |
| -------- | ----- |
| Precision | 0.998 |
| Recall    | 0.940 |
| mAP50     | 0.977 |
| mAP50-95  | 0.757 |

Per-epoch trend, from `runs/local-train/results.csv`:

| epoch | box_loss | mAP50  | mAP50-95 |
| ----- | -------- | ------ | -------- |
| 1     | 1.110    | 0.0734 | 0.0242   |
| 2     | 1.159    | 0.5922 | 0.3449   |
| 3     | 1.151    | 0.8287 | 0.5840   |
| 5     | 1.028    | 0.9511 | 0.6816   |
| 7     | 0.952    | 0.9723 | 0.7022   |
| 10    | 0.805    | 0.9775 | 0.7583   |

Loss falls monotonically after epoch 2 and mAP50-95 is still climbing at epoch
10 — more epochs would likely still help, but the pipeline is the goal here.

Outputs in `runs/local-train/`: `weights/best.pt` and `weights/last.pt`
(5.4 MB each), plus PR/F1 curves, confusion matrices, and labelled vs predicted
validation batches.

**Platform note** — Ultralytics reports `Using 0 dataloader workers` on Windows
regardless of `workers: 4`. The setting is inert here but will take effect on
Linux under Kubeflow.

---

### Test and evaluate

`best.pt` is reloaded from disk rather than reused from memory, so the
evaluation covers the artifact that would actually be deployed.

```python
best = YOLO(save_dir / "weights" / "best.pt")
metrics = best.val(data=data_yaml, imgsz=416, batch=8, device="cpu")
```

```text
mAP50      0.9582
mAP50-95   0.7506
precision  0.9909
recall     0.9355
```

**Where recall fails.** Recall (0.936) trails precision (0.991), so the model
misses plates rather than inventing them. Counting detections against labels
per image:

| plates/img | images | labelled | detected | missed |
| ---------- | ------ | -------- | -------- | ------ |
| 1          | 106    | 106      | 108      | 2      |
| 2          | 5      | 10       | 6        | 4      |

6 of 116 plates missed (5.2%). The misses concentrate in multi-plate images:
those hold 8.6% of labels but account for 67% of misses — a 40% per-plate miss
rate, against 1.9% on single-plate images.

Cause is the training distribution, not the architecture: `boxes_per_image_mean`
is 1.03, so the model rarely saw a second plate. Worth knowing before serving,
where a missed second plate is a silent failure.

The notebook also plots predictions (red) against ground truth (green) on
sample validation images.

**Reproducibility note** — re-running the notebook retrains from scratch, and
CPU thread scheduling makes results vary slightly despite `seed: 0`. The first
run gave mAP50 0.977 / recall 0.940; the second, 0.958 / 0.936.
