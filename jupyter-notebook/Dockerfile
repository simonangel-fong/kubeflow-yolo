FROM python:3.12-slim

# update system
RUN apt-get update && apt-get install -y --no-install-recommends && apt-get install -y git \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# library
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir jupyterlab mlflow

# ONNX export and the parity check against serve/inference.py.
# onnxslim is what ultralytics shells out to for export(simplify=True).
RUN pip install --no-cache-dir onnx onnxslim onnxruntime

# env var
ENV YOLO_CONFIG_DIR=/workspace/.ultralytics
ENV MPLCONFIGDIR=/tmp/matplotlib

EXPOSE 8888

CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--allow-root", \
     "--NotebookApp.token=", \
     "--NotebookApp.password="]
