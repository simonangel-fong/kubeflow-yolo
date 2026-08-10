# Predictor image for the KServe InferenceService.
#   docker build -f serve/Dockerfile -t simonangelfong/kubeflow-yolo-serve:v0.1.0 .
#
# ~400 MB against the ~2 GB a torch+ultralytics image costs: onnxruntime and
# opencv-headless are the only heavy dependencies.

FROM python:3.12-slim

# opencv-python-headless still needs libglib for its core; libgl is not
# required by the headless build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY serve/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY serve/ ./serve/

# Writable by the arbitrary UID the restricted PSS namespace assigns.
ENV MODEL_DIR=/mnt/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# KServe routes to 8080 on the predictor container by default.
CMD ["uvicorn", "serve.app:app", "--host", "0.0.0.0", "--port", "8080"]
