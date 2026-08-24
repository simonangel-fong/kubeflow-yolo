# Training image. Runs train-job/src/train.py in the cluster; used as the Katib
# trial container, where the search parameters arrive as CLI flags.
#
# GPU (default) -- trials run on the g5.xlarge nodepool with --device=0:
#   docker build -f train-job/Dockerfile \
#     -t <registry>/kubeflow-yolo-train:v0.2.0 .
#
# CPU -- smaller image, --device=cpu:
#   docker build -f train-job/Dockerfile --build-arg FLAVOR=cpu \
#     --build-arg BASE=python:3.12-slim \
#     -t <registry>/kubeflow-yolo-train:v0.2.0-cpu .
#
# Build context is the repo root.

ARG BASE=nvidia/cuda:13.0.1-runtime-ubuntu24.04
FROM ${BASE}

# cpu or gpu; selects requirements.<FLAVOR>.txt
ARG FLAVOR=gpu

# The CUDA images ship no python; python:3.12-slim already has it and skips this.
RUN if ! command -v python3 >/dev/null; then \
        apt-get update && apt-get install -y --no-install-recommends \
            python3 python3-pip python3-venv \
        && rm -rf /var/lib/apt/lists/*; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 marks its python as externally managed, so install into a venv
# rather than fighting PEP 668.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /app

COPY train-job/requirements.${FLAVOR}.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Writable by the arbitrary UID the restricted PSS namespace assigns.
ENV YOLO_CONFIG_DIR=/tmp/ultralytics
ENV MPLCONFIGDIR=/tmp/matplotlib

# train.py imports `src.data_loader`, so src/ must sit next to it on the path
COPY train-job/src/ ./src/
COPY train-job/configs/train.yaml ./configs/train.yaml

# The pretrained checkpoint named in configs/train.yaml is fetched by
# ultralytics on first use and cached under YOLO_CONFIG_DIR.

ENTRYPOINT ["python", "-m", "src.train"]
