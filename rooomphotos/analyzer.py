from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import imagehash
import numpy as np
import open_clip
import torch
from PIL import Image, ImageOps

from .config import CATEGORY_PROMPTS, CATEGORY_QUOTAS, CLIP_DUPLICATE_SIMILARITY, JUNK_CONFIDENCE_MARGIN, JUNK_PROMPTS, MIN_HEIGHT, MIN_SHARPNESS, MIN_WIDTH, PHASH_DISTANCE


@dataclass
class Candidate:
    file_id: str
    name: str
    path: Path
    width: int = 0
    height: int = 0
    sharpness: float = 0.0
    brightness: float = 0.0
    shadow_clip: float = 0.0
    highlight_clip: float = 0.0
    quality: float = 0.0
    category: str = "unknown"
    category_score: float = 0.0
    junk_label: str = ""
    junk_score: float = 0.0
    phash: imagehash.ImageHash | None = None
    embedding: np.ndarray | None = field(default=None, repr=False)
    rejected: bool = False
    selected: bool = False
    reason: str = ""

    def report_dict(self) -> dict:
        return {
            "file_id": self.file_id, "name": self.name, "width": self.width, "height": self.height,
            "category": self.category, "category_score": round(self.category_score, 4),
            "quality_score": round(self.quality, 4), "sharpness": round(self.sharpness, 2),
            "brightness": round(self.brightness, 4), "shadow_clip": round(self.shadow_clip, 4),
            "highlight_clip": round(self.highlight_clip, 4), "junk_label": self.junk_label,
            "junk_score": round(self.junk_score, 4), "selected": self.selected,
            "rejected": self.rejected, "reason": self.reason,
        }


class PhotoAnalyzer:
    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
        self.model = self.model.to(self.device).eval()
        self.tokenizer = open_clip.get_tokenizer(model_name)
        self.category_names = list(CATEGORY_PROMPTS)
        self.junk_names = list(JUNK_PROMPTS)
        prompts = list(CATEGORY_PROMPTS.values()) + list(JUNK_PROMPTS.values())
        with torch.inference_mode():
            tokens = self.tokenizer(prompts).to(self.device)
            text_features = self.model.encode_text(tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
        self.text_features = text_features
        self.qr_detector = cv2.QRCodeDetector()

    @staticmethod
    def open_oriented(path: Path) -> Image.Image:
        return ImageOps.exif_transpose(Image.open(path)).convert("RGB")

    @staticmethod
    def quality_metrics(image: Image.Image) -> tuple[float, float, float, float, float]:
        arr = np.asarray(image)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean() / 255.0)
        shadow_clip = float((gray <= 8).mean())
        highlight_clip = float((gray >= 247).mean())
        mp = image.width * image.height / 1_000_000
        resolution = min(1.0, math.sqrt(max(mp, 0.01) / 8.0))
        sharp = min(1.0, math.log1p(sharpness) / math.log1p(550.0))
        exposure = max(0.0, 1.0 - abs(brightness - 0.56) * 1.7 - shadow_clip * 1.8 - highlight_clip * 1.8)
        landscape = 1.0 if image.width >= image.height else 0.45
        quality = 0.35 * sharp + 0.30 * exposure + 0.20 * resolution + 0.15 * landscape
        return sharpness, brightness, shadow_clip, highlight_clip, float(np.clip(quality, 0.0, 1.0))

    def analyze(self, file_id: str, name: str, path: Path) -> Candidate:
        c = Candidate(file_id=file_id, name=name, path=path)
        try:
            image = self.open_oriented(path)
        except Exception as exc:
            c.rejected, c.reason = True, f"decode_error: {exc}"
            return c
        c.width, c.height = image.size
        c.sharpness, c.brightness, c.shadow_clip, c.highlight_clip, c.quality = self.quality_metrics(image)
        c.phash = imagehash.phash(image)

        tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            feat = self.model.encode_image(tensor)
            feat /= feat.norm(dim=-1, keepdim=True)
            sims = (feat @ self.text_features.T).squeeze(0).float().cpu().numpy()
        c.embedding = feat.squeeze(0).float().cpu().numpy()
        category_scores = sims[: len(self.category_names)]
        junk_scores = sims[len(self.category_names):]
        ci, ji = int(np.argmax(category_scores)), int(np.argmax(junk_scores))
        c.category, c.category_score = self.category_names[ci], float(category_scores[ci])
        c.junk_label, c.junk_score = self.junk_names[ji], float(junk_scores[ji])

        try:
            found, points = self.qr_detector.detect(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR))
        except Exception:
            found, points = False, None
        if bool(found) or points is not None:
            c.rejected, c.reason = True, "QRコードを検出"
            return c

        short_side, long_side = sorted((c.width, c.height))
        if long_side < MIN_WIDTH or short_side < MIN_HEIGHT:
            c.rejected, c.reason = True, "解像度不足"
        elif c.sharpness < MIN_SHARPNESS:
            c.rejected, c.reason = True, "ブレ・ピンぼけ"
        elif c.category != "layout" and c.junk_score > c.category_score + JUNK_CONFIDENCE_MARGIN:
            c.rejected, c.reason = True, f"不要画像候補: {c.junk_label}"
        elif c.brightness < 0.12:
            c.rejected, c.reason = True, "極端に暗い"
        elif c.highlight_clip > 0.42:
            c.rejected, c.reason = True, "白飛びが多い"
        else:
            if c.width < c.height:
                c.quality = max(0.0, c.quality - 0.12)
            c.reason = "選定候補"
        return c


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def deduplicate(candidates: list[Candidate]) -> list[Candidate]:
    eligible = sorted((c for c in candidates if not c.rejected), key=lambda c: (c.quality, c.category_score), reverse=True)
    kept: list[Candidate] = []
    for c in eligible:
        duplicate_of = None
        for prior in kept:
            phash_close = c.phash is not None and prior.phash is not None and (c.phash - prior.phash) <= PHASH_DISTANCE
            clip_close = c.embedding is not None and prior.embedding is not None and cosine(c.embedding, prior.embedding) >= CLIP_DUPLICATE_SIMILARITY
            if phash_close or clip_close:
                duplicate_of = prior
                break
        if duplicate_of:
            c.rejected, c.reason = True, f"類似・重複: {duplicate_of.name} を優先"
        else:
            kept.append(c)
    return candidates


def select_balanced(candidates: list[Candidate], min_selected: int = 15, max_selected: int = 28) -> list[Candidate]:
    pool = [c for c in candidates if not c.rejected]
    by_category: dict[str, list[Candidate]] = {}
    for c in pool:
        by_category.setdefault(c.category, []).append(c)
    for values in by_category.values():
        values.sort(key=lambda c: c.quality * 0.72 + c.category_score * 0.28, reverse=True)

    selected: list[Candidate] = []
    ids: set[str] = set()
    order = ["living", "bedroom", "kitchen", "bathroom", "toilet", "entrance", "exterior", "workspace", "amenity", "view", "layout"]
    for category in order:
        values = by_category.get(category, [])
        if values and len(selected) < max_selected:
            c = values[0]
            c.selected, c.reason = True, f"採用: {category} の代表写真"
            selected.append(c); ids.add(c.file_id)

    for rank in range(1, max(CATEGORY_QUOTAS.values())):
        for category in order:
            if len(selected) >= max_selected:
                break
            values, quota = by_category.get(category, []), CATEGORY_QUOTAS.get(category, 1)
            if rank < quota and rank < len(values):
                c = values[rank]
                if c.file_id not in ids:
                    c.selected, c.reason = True, f"採用: {category} の追加構図"
                    selected.append(c); ids.add(c.file_id)

    if len(selected) < min_selected:
        remaining = sorted((c for c in pool if c.file_id not in ids), key=lambda c: c.quality * 0.78 + c.category_score * 0.22, reverse=True)
        for c in remaining:
            if len(selected) >= min_selected or len(selected) >= max_selected:
                break
            c.selected, c.reason = True, "採用: 品質・多様性補完"
            selected.append(c); ids.add(c.file_id)

    for c in pool:
        if c.file_id not in ids:
            c.reason = "除外: 掲載枚数・カテゴリ重複のため優先度外"
    return selected
