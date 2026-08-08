## Stage 2 — local track

- deploy jupyter notebook and mlflow with docker compose
- train the same model
- track training with mlflow
- try hyperparameter tunning with mlflow

Same model and data as stage 1. What changes is where training runs
(container, not venv) and that runs are recorded instead of lost.

---

## Stack

- docker compose
- Jupyter (containerised)
- mlflow

---

## Phases

| #   | Phase                 | Description                                        | Done when                                     |
| --- | --------------------- | -------------------------------------------------- | --------------------------------------------- |
| 1   | compose stack         | jupyter + mlflow in one compose file, data mounted | both UIs reachable, notebook sees `data/raw/` |
| 2   | train in container    | rerun the stage 1 notebook unchanged               | metrics match stage 1 within noise            |
| 3   | track training        | log params, metrics and weights to mlflow          | run appears in mlflow with `best.pt` attached |
| 4   | hyperparameter tuning | several runs over a small search space             | runs comparable side by side in mlflow        |

### Notes

- mlflow state must outlive `docker compose down` — decide the backing store in
  phase 1, not after losing runs.
- Phase 2 proves the container reaches the data and trains correctly; that run
  is untracked and disposable.
- `configs/data.yaml` holds an absolute host path. Container paths differ, so
  it has to be regenerated inside the container.
- Tracking code belongs in `src/`, not pasted between notebooks.

---

## Output

`docs/02-local-track.md` — write-up of the stage.
