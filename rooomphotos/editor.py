from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .config import PlatformPreset


def _gray_world_white_balance(rgb: np.ndarray) -> np.ndarray:
    work = rgb.astype(np.float32)
    means = work.reshape(-1, 3).mean(axis=0)
    target = float(means.mean())
    gains = np.clip(target / (means + 1e-6), 0.90, 1.10)
    return np.clip(work * gains, 0, 255).astype(np.uint8)


def _gentle_exposure(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mean = max(float(gray.mean() / 255.0), 0.02)
    target = 0.55
    gamma = np.log(target) / np.log(mean) if mean not in (0.0, 1.0) else 1.0
    gamma = float(np.clip(gamma, 0.86, 1.14))
    table = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(rgb, table)


def _local_contrast(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.35, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)


def enhance(path) -> Image.Image:
    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    rgb = np.asarray(image)
    rgb = _gray_world_white_balance(rgb)
    rgb = _gentle_exposure(rgb)
    rgb = _local_contrast(rgb)
    image = Image.fromarray(rgb)
    image = ImageEnhance.Color(image).enhance(1.03)
    image = ImageEnhance.Contrast(image).enhance(1.02)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=65, threshold=3))
    return image


def render_variant(image: Image.Image, preset: PlatformPreset) -> Image.Image:
    if preset.height is None:
        if image.width <= preset.width:
            return image.copy()
        ratio = preset.width / image.width
        size = (preset.width, max(1, round(image.height * ratio)))
        return image.resize(size, Image.Resampling.LANCZOS)

    target = (preset.width, preset.height)
    if preset.crop:
        # Content-aware crop is intentionally not generative: only a centered geometric crop.
        return ImageOps.fit(image, target, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    return image.resize(target, Image.Resampling.LANCZOS)


def jpeg_bytes(image: Image.Image, quality: int = 92) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(
        output,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling=0,
    )
    return output.getvalue()
