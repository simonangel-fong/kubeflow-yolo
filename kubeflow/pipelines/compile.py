"""
Compile the pipeline to yolo_pipeline.yaml.

    python compile.py

Runs anywhere the kfp SDK is installed -- no cluster needed. The generated
yaml is what the KFP API consumes, so it is worth committing: it is the record
of exactly what a given run executed.
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
