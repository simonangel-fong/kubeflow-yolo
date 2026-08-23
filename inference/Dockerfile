# Predictor image for the KServe InferenceService.
#   docker build -f inference/Dockerfile -t simonangelfong/kubeflow-yolo-inference:v0.1.1-cpu .

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY inference/src/ ./src/
COPY models/ /mnt/models/

ENV MODEL_DIR=/mnt/models
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# KServe routes to 8080 on the predictor container by default.
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8080"]
