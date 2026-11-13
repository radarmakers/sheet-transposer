"""Make clean engraved pages look like scans or phone photos (deterministic per seed)."""

import io

import albumentations as A
import cv2
import numpy as np
from PIL import Image

VARIANTS = ("clean", "scan", "phone")

_WHITE = 255
_PAPER_MARGIN = 0.12  # white border added round the engraved page, like the edge of real paper


def _pipeline(variant: str, seed: int, border_px: int) -> A.Compose:
    paper = A.Pad(padding=border_px, fill=_WHITE, p=1)
    if variant == "scan":
        transforms = [
            A.Rotate(limit=2, border_mode=cv2.BORDER_CONSTANT, fill=_WHITE, p=1),
            A.GaussNoise(std_range=(0.01, 0.03), p=1),
            A.ImageCompression(quality_range=(70, 85), p=1),
        ]
    elif variant == "phone":
        transforms = [
            A.Perspective(scale=(0.02, 0.05), fill=_WHITE, p=1),
            A.Rotate(limit=4, border_mode=cv2.BORDER_CONSTANT, fill=_WHITE, p=1),
            A.Illumination(mode="linear", intensity_range=(0.05, 0.2), p=1),
            A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=1),
            A.GaussianBlur(blur_limit=(3, 5), p=1),
            A.Downscale(scale_range=(0.6, 0.8), p=1),
            A.ImageCompression(quality_range=(50, 70), p=1),
        ]
    else:
        raise ValueError(f"unknown variant {variant!r}")
    return A.Compose([paper, *transforms], seed=seed)


def degrade(png: bytes, variant: str, seed: int) -> bytes:
    """Return PNG bytes of the page degraded as `variant` ('clean' returns the input)."""
    if variant == "clean":
        return png
    pixels = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    border_px = int(_PAPER_MARGIN * max(pixels.shape[:2]))
    degraded = _pipeline(variant, seed, border_px)(image=pixels)["image"]
    buffer = io.BytesIO()
    Image.fromarray(degraded).save(buffer, "PNG")
    return buffer.getvalue()
