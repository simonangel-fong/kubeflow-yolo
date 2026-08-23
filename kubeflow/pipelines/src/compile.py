"""
Compile the pipeline to yolo_pipeline.yaml.
    python compile.py
"""

from pathlib import Path
from kfp import compiler
from yolo_pipeline import yolo_pipeline

OUTPUT = Path(__file__).parent / "yolo_pipeline.yaml"


def main() -> int:
    compiler.Compiler().compile(yolo_pipeline, str(OUTPUT))
    print("compiled", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
