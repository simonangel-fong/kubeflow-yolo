"""Build the YOLO train/val split from the raw dataset.

`data/raw/` is a flat directory of image + label pairs sharing a basename,
already lowercased and underscore-separated:

    data/raw/ford_focus_with_license_plate_12.jpeg
    data/raw/ford_focus_with_license_plate_12.txt

This produces the layout Ultralytics expects:

    data/processed/{train,val}/{images,labels}/
"""

from __future__ import annotations

import random
import shutil
from collections import Counter
from pathlib import Path

IMAGE_SUFFIXES = {".jpeg", ".jpg", ".png"}

# Not a label: the class-name list emitted by the labelling tool.
CLASSES_FILENAME = "classes.txt"


def find_pairs(raw_dir: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Pair images with labels by basename.

    Returns (pairs, images_without_labels, labels_without_images). Ultralytics
    trains happily on a mismatched directory, so orphans must be surfaced
    rather than silently dropped.
    """
    images = {p.stem: p for p in raw_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES}
    labels = {
        p.stem: p
        for p in raw_dir.iterdir()
        if p.suffix.lower() == ".txt" and p.name != CLASSES_FILENAME
    }

    pairs = [(images[s], labels[s]) for s in sorted(images.keys() & labels.keys())]
    orphan_images = [images[s] for s in sorted(images.keys() - labels.keys())]
    orphan_labels = [labels[s] for s in sorted(labels.keys() - images.keys())]
    return pairs, orphan_images, orphan_labels


def summarize(raw_dir: Path) -> dict[str, object]:
    """Dataset facts worth knowing before training."""
    pairs, orphan_images, orphan_labels = find_pairs(raw_dir)

    boxes_per_image: list[int] = []
    class_counts: Counter[str] = Counter()
    malformed: list[str] = []

    for _, label in pairs:
        lines = [ln for ln in label.read_text().splitlines() if ln.strip()]
        boxes_per_image.append(len(lines))
        for ln in lines:
            parts = ln.split()
            # YOLO format: class cx cy w h, all normalised to 0-1.
            if len(parts) != 5 or not all(0 <= float(v) <= 1 for v in parts[1:]):
                malformed.append(f"{label.name}: {ln}")
            else:
                class_counts[parts[0]] += 1

    suffixes = Counter(img.suffix.lower() for img, _ in pairs)
    return {
        "pairs": len(pairs),
        "orphan_images": [p.name for p in orphan_images],
        "orphan_labels": [p.name for p in orphan_labels],
        "boxes_total": sum(boxes_per_image),
        "boxes_per_image_min": min(boxes_per_image, default=0),
        "boxes_per_image_max": max(boxes_per_image, default=0),
        "boxes_per_image_mean": round(sum(boxes_per_image) / len(boxes_per_image), 2)
        if boxes_per_image
        else 0,
        "images_without_boxes": sum(1 for n in boxes_per_image if n == 0),
        "class_counts": dict(class_counts),
        "suffixes": dict(suffixes),
        "malformed": malformed,
    }


def build_split(
    raw_dir: Path,
    out_dir: Path,
    val_fraction: float = 0.2,
    limit: int | None = None,
    seed: int = 0,
) -> dict[str, int]:
    """Copy paired files into out_dir/{train,val}/{images,labels}.

    `limit` caps the number of pairs used -- this stage optimises for a working
    pipeline, not accuracy. Copies rather than moves, so the split can be
    rebuilt with a different seed and data/raw stays intact.
    """
    pairs, orphan_images, orphan_labels = find_pairs(raw_dir)
    if not pairs:
        raise RuntimeError(f"no image/label pairs found in {raw_dir}")

    rng = random.Random(seed)
    rng.shuffle(pairs)
    if limit is not None:
        pairs = pairs[:limit]

    n_val = round(len(pairs) * val_fraction)
    splits = {"val": pairs[:n_val], "train": pairs[n_val:]}

    if out_dir.exists():
        shutil.rmtree(out_dir)

    for split, items in splits.items():
        for kind in ("images", "labels"):
            (out_dir / split / kind).mkdir(parents=True, exist_ok=True)
        for image, label in items:
            shutil.copy2(image, out_dir / split / "images" / image.name)
            shutil.copy2(label, out_dir / split / "labels" / label.name)

    return {
        "train": len(splits["train"]),
        "val": len(splits["val"]),
        "orphan_images": len(orphan_images),
        "orphan_labels": len(orphan_labels),
    }


def verify_split(out_dir: Path) -> dict[str, int]:
    """Re-derive pairing from disk, so a broken split fails here, not mid-training."""
    counts: dict[str, int] = {}
    for split in ("train", "val"):
        images = {p.stem for p in (out_dir / split / "images").iterdir()}
        labels = {p.stem for p in (out_dir / split / "labels").iterdir()}
        if images != labels:
            raise RuntimeError(
                f"{split}: unpaired -- "
                f"images only {sorted(images - labels)[:5]}, "
                f"labels only {sorted(labels - images)[:5]}"
            )
        counts[split] = len(images)

    overlap = {p.stem for p in (out_dir / "train" / "images").iterdir()} & {
        p.stem for p in (out_dir / "val" / "images").iterdir()
    }
    if overlap:
        raise RuntimeError(f"train/val leakage: {sorted(overlap)[:5]}")

    return counts


def write_data_yaml(path: Path, processed_dir: Path, names: list[str]) -> Path:
    """Write the dataset descriptor Ultralytics reads.

    `path` is absolute so training works regardless of the caller's cwd.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"path: {processed_dir.as_posix()}\n"
        "train: train/images\n"
        "val: val/images\n"
        f"nc: {len(names)}\n"
        f"names: {names}\n"
    )
    return path
