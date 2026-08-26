# Train-job image

FROM nvidia/cuda:13.0.1-runtime-ubuntu24.04

# The CUDA images ship no python.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

COPY train-job/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV MPLCONFIGDIR=/tmp/matplotlib

COPY train-job/src/ ./src/
COPY train-job/configs/train.yaml ./configs/train.yaml

ENTRYPOINT ["python", "-m", "src.train"]
