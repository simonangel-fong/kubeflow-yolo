# Predictor image for the KServe InferenceService.
#   docker build -f inference/Dockerfile -t simonangelfong/kubeflow-yolo-inference:v0.1.1-cpu .
#
# ~400 MB against the ~2 GB a torch+ultralytics image costs: onnxruntime and
# opencv-headless are the only heavy dependencies.
#
# The model ships in the image rather than being fetched at startup. KServe's
# pod-mutator webhook -- the thing that injects the storage initializer -- is
# scoped to namespaces without a control-plane label, so a STORAGE_URI is
# silently ignored in kubeflow and /mnt/models stays empty. Baking the model in
# removes that dependency entirely; the cost is a rebuild per retrain.

FROM python:3.12-slim

# opencv-python-headless still needs libglib for its core; libgl is not
# required by the headless build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY inference/src/ ./src/

# The exported model, verified by inference/export.py before it lands here.
# Last layer, so a code change does not re-copy 10 MB and a model swap does not
# invalidate the pip install above.
COPY models/ /mnt/models/

ENV MODEL_DIR=/mnt/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# KServe routes to 8080 on the predictor container by default.
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]
