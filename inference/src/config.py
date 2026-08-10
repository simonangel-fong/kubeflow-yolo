"""
Runtime settings
"""

from __future__ import annotations

import os
from pathlib import Path

# model mount point
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/mnt/models"))

# model name: endpoints /v1/models/{MODEL_NAME}
MODEL_NAME = os.environ.get("MODEL_NAME", "yolo-car-plate")

# Detection defaults; each request may override them per instance.
CONF_THRESHOLD = float(os.environ.get("CONF_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.environ.get("IOU_THRESHOLD", "0.45"))

# Cap decoded image bytes
MAX_IMAGE_BYTES = int(os.environ.get("MAX_IMAGE_BYTES", 10 * 1024 * 1024))
