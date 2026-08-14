from __future__ import annotations

import csv
import io
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from .analyzer import Candidate, PhotoAnalyzer, deduplicate, select_balanced
from .config import PLATFORMS
from .drive import download_file, ensure_output_tree, extract_folder_id, get_drive_service, list_images, upload_bytes, upload_text
from .editor import enhance, jpeg_bytes, render_variant


CATEGORY_PRIORITY = {
    "living": 0, "exterior": 1, "bedroom": 2, "view": 3, "kitchen": 4,
    "bathroom": 5, "workspace": 6, "amenity": 7, "entrance": 8,
    "toilet": 9, "layout": 10,
}


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r'[<>:"/\\|?*]+', "_", stem)
    stem = re.sub(r"\s+", "_", stem).strip("._")
    return stem[:100] or "photo"


def _ext_for_mime(mime: str) -> str:
    return {"image/png": ".png", "image/webp": ".webp"}.get(mime, ".jpg")


def _csv_report(candidates: list[Candidate]) -> str:
    rows = [c.report_dict() for c in candidates]
    if not rows:
        return ""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _hero_sort(c: Candidate):
    return (CATEGORY_PRIORITY.get(c.category, 99), -(c.quality * 0.8 + c.category_score * 0.2))


def _platform_selection(key: str, selected: list[Candidate], candidates: list[Candidate], min_selected: int) -> list[Candidate]:
    output = list(selected)
    if key == "instabase":
        # Instabase explicitly disallows bed photos when they represent lodging/overnight use.
        output = [c for c in output if c.category != "bedroom"]
        output_ids = {c.file_id for c in output}
        if len(output) < min_selected:
            extras = sorted(
                (
                    c for c in candidates
                    if not c.rejected and c.category != "bedroom" and c.file_id not in output_ids
                ),
                key=lambda c: (c.quality * 0.8 + c.category_score * 0.2),
                reverse=True,
            )
            output.extend(extras[: max(0, min_selected - len(output))])
    return sorted(output, key=_hero_sort)


def run_drive_pipeline(
    folder_url_or_id: str,
    credentials: str | None = None,
    token_file: str | None = None,
    output_folder_name: str = "リスティング用_加工済み",
    min_selected: int = 15,
    max_selected: int = 28,
    dry_run: bool = False,
    progress=None,
) -> dict:
    if min_selected < 1 or max_selected < min_selected:
        raise ValueError("min_selected / max_selected の指定が不正です")

    source_folder_id = extract_folder_id(folder_url_or_id)
    service = get_drive_service(credentials, token_file)
    metadata = list_images(service, source_folder_id)
    if not metadata:
        raise RuntimeError("対象フォルダに JPEG / PNG / WebP が見つかりません")

    analyzer = PhotoAnalyzer()
    candidates: list[Candidate] = []

    with tempfile.TemporaryDirectory(prefix="rooomphotos_") as temp_dir:
        temp = Path(temp_dir)
        for index, item in enumerate(metadata, start=1):
            local = temp / f"{index:04d}_{_safe_stem(item['name'])}{_ext_for_mime(item['mimeType'])}"
            if progress:
                progress(f"解析 {index}/{len(metadata)}: {item['name']}")
            download_file(service, item["id"], local)
            candidates.append(analyzer.analyze(item["id"], item["name"], local))

        deduplicate(candidates)
        selected = select_balanced(candidates, min_selected=min_selected, max_selected=max_selected)
        selected = sorted(selected, key=_hero_sort)

        report_csv = _csv_report(candidates)
        report_json = json.dumps([c.report_dict() for c in candidates], ensure_ascii=False, indent=2)

        summary = {
            "source_folder_id": source_folder_id,
            "total_images": len(candidates),
            "selected_images": len(selected),
            "rejected_images": sum(1 for c in candidates if c.rejected),
            "selected": [c.report_dict() for c in selected],
            "output_folder_id": None,
            "output_folder_name": None,
        }
        if dry_run:
            return summary

        run_name = f"{output_folder_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        folder_map = ensure_output_tree(
            service,
            source_folder_id,
            run_name,
            [preset.name for preset in PLATFORMS.values()],
        )
        summary["output_folder_id"] = folder_map["root"]
        summary["output_folder_name"] = run_name

        platform_lists: dict[str, list[Candidate]] = {}
        for key in PLATFORMS:
            if key == "master":
                continue
            platform_lists[key] = _platform_selection(key, selected, candidates, min_selected)

        master_union: list[Candidate] = []
        union_ids: set[str] = set()
        for values in platform_lists.values():
            for c in values:
                if c.file_id not in union_ids:
                    union_ids.add(c.file_id)
                    master_union.append(c)
        platform_lists["master"] = sorted(master_union, key=_hero_sort)

        rendered_cache: dict[str, object] = {}
        for key, preset in PLATFORMS.items():
            values = platform_lists[key]
            for order, candidate in enumerate(values, start=1):
                if progress:
                    progress(f"出力 {preset.name} {order}/{len(values)}: {candidate.name}")
                base = rendered_cache.get(candidate.file_id)
                if base is None:
                    base = enhance(candidate.path)
                    rendered_cache[candidate.file_id] = base
                variant = render_variant(base, preset)
                filename = f"{order:02d}_{candidate.category}_{_safe_stem(candidate.name)}.jpg"
                upload_bytes(service, folder_map[preset.name], filename, jpeg_bytes(variant, preset.quality), "image/jpeg")

        upload_text(service, folder_map["root"], "選定レポート.csv", report_csv, "text/csv")
        upload_text(service, folder_map["root"], "選定レポート.json", report_json, "application/json")
        return summary
