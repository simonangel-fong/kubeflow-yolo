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

**`configs/data.yaml`**: data config file
**`configs/train.yaml`**: train config file

**Model**:

- `yolo11n.pt`: the smallest variant, pretrained.

---

### Train model
