"""Deterministic, explicitly synthetic visual fixtures; not trained-model output."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def generate_visual_fixtures(output_dir: Path) -> dict[str, object]:
    """Render a paired clean/scratched bottle and its exact pixel-difference response."""
    output_dir.mkdir(parents=True, exist_ok=True)
    size = 512
    shape = Image.new("L", (size, size))
    draw = ImageDraw.Draw(shape)
    draw.rounded_rectangle((148, 150, 364, 462), radius=36, fill=255)
    draw.polygon([(148, 185), (194, 112), (194, 65), (318, 65), (318, 112), (364, 185)], fill=255)
    yy, xx = np.mgrid[:size, :size]
    rng = np.random.default_rng(42)
    cylinder = 75 + 120 * np.exp(-(((xx - 225) / 75) ** 2))
    texture = rng.normal(0, 1.3, (size, size))
    background = np.full((size, size), 235, dtype=float)
    clean_array = (
        np.where(np.array(shape) > 0, cylinder + texture, background).clip(0, 255).astype(np.uint8)
    )
    clean = Image.fromarray(clean_array).convert("RGB")
    scratch = Image.new("L", (size, size))
    draw = ImageDraw.Draw(scratch)
    draw.line([(221, 245), (238, 264), (256, 284), (269, 309), (294, 331)], fill=255, width=4)
    draw.line([(225, 247), (243, 267), (260, 285), (273, 308), (296, 329)], fill=150, width=2)
    scratched = np.array(clean).copy()
    alpha = np.asarray(scratch, dtype=float) / 255
    scratched = (scratched * (1 - alpha[..., None]) + 247 * alpha[..., None]).astype(np.uint8)
    # This is a measured residual against the known clean fixture, NOT model inference.
    response = np.abs(scratched.astype(float) - np.asarray(clean, dtype=float)).mean(axis=2)
    response /= max(float(response.max()), 1.0)
    smooth = (
        np.asarray(
            Image.fromarray((response * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)),
            dtype=float,
        )
        / 255
    )
    smooth /= max(float(smooth.max()), 1e-8)
    heat = np.stack(
        [np.clip(2 * smooth, 0, 1), np.clip(2 * smooth - 1, 0, 1), np.clip(1 - 2 * smooth, 0, 1)],
        axis=-1,
    )
    clean.save(output_dir / "bottle-clean.png")
    Image.fromarray(scratched).save(output_dir / "bottle-scratch.png")
    scratch.save(output_dir / "bottle-mask.png")
    Image.fromarray((heat * 255).astype(np.uint8)).save(output_dir / "bottle-response.png")
    metadata: dict[str, object] = {
        "fixture_type": "controlled_synthetic",
        "seed": 42,
        "image": "bottle-scratch.png",
        "clean_reference": "bottle-clean.png",
        "mask": "bottle-mask.png",
        "response": "bottle-response.png",
        "response_method": (
            "absolute RGB pixel difference from clean reference, "
            "mean channels, Gaussian sigma=6, max normalization"
        ),
        "trained_model": False,
        "dataset_sample": False,
        "claim_boundary": (
            "UI fixture only; not MVTec dataset imagery, "
            "not detector output, no factory RCA validation"
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return metadata
