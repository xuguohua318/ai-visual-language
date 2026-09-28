from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import unicodedata
import zipfile
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from pypdf import PdfReader


MISSING_ABSTRACT_IMAGES = {49, 50, 51, 65, 69, 72, 115, 120}
MODULE_SLUGS = {
    "视觉基础": "visual-foundations",
    "摄影与镜头": "cinematography",
    "运动与变化": "motion-change",
    "剪辑与时间": "editing-time",
    "科技与可视化": "technology-visualization",
    "抽象视觉": "abstract-visuals",
    "AI表达": "ai-expression",
}


def clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value or "visual"


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_workbook_data(workbook_path: Path):
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)

    terms = []
    abstract_index = 0
    for row in workbook["总词库"].iter_rows(min_row=2, values_only=True):
        module, category, zh, en, _, explanation, prompt, pairings, *_ = tuple(row) + (None,) * 9
        if not clean(zh):
            continue
        if clean(module) == "抽象视觉":
            abstract_index += 1
            local_index = abstract_index
        else:
            local_index = None
        term_id = f"AVL-{len(terms) + 1:04d}"
        terms.append(
            {
                "id": term_id,
                "module": clean(module),
                "moduleSlug": MODULE_SLUGS.get(clean(module), slugify(clean(module))),
                "category": clean(category),
                "nameZh": clean(zh),
                "nameEn": clean(en),
                "plainExplanation": clean(explanation),
                "promptExample": clean(prompt),
                "commonPairings": clean(pairings),
                "abstractIndex": local_index,
                "image": None,
            }
        )

    templates = []
    for index, row in enumerate(workbook["提示词模板"].iter_rows(min_row=2, values_only=True), start=1):
        kind, name, structure, example, use_case, *_ = tuple(row) + (None,) * 5
        if not clean(kind):
            continue
        templates.append(
            {
                "id": f"TPL-{len(templates) + 1:03d}",
                "type": clean(kind),
                "name": clean(name),
                "recommendedStructure": clean(structure),
                "copyReadyExample": clean(example),
                "useCase": clean(use_case),
            }
        )

    mappings = []
    for row in workbook["抽象意象映射"].iter_rows(min_row=2, values_only=True):
        concept, carrier, action, explanation, prompt, pairings, *_ = tuple(row) + (None,) * 6
        if not clean(concept):
            continue
        mappings.append(
            {
                "id": f"MAP-{len(mappings) + 1:03d}",
                "concept": clean(concept),
                "visualCarrier": clean(carrier),
                "coreAction": clean(action),
                "plainExplanation": clean(explanation),
                "promptExample": clean(prompt),
                "commonPairings": clean(pairings),
            }
        )

    return terms, templates, mappings


def match_pdf_images(pdf_path: Path):
    reader = PdfReader(str(pdf_path))
    placements = []
    with pdfplumber.open(str(pdf_path)) as plumber_pdf:
        for page_number, (pdf_page, layout_page) in enumerate(zip(reader.pages, plumber_pdf.pages), start=1):
            boxes = sorted(layout_page.images, key=lambda item: (item["top"], item["x0"]))
            images = list(pdf_page.images)
            if len(boxes) != len(images):
                raise RuntimeError(f"Page {page_number}: layout/image count mismatch")
            for box, embedded in zip(boxes, images):
                slot = min(range(4), key=lambda i: abs(box["top"] - (55.1 + 153.75 * i))) + 1
                abstract_number = (page_number - 1) * 4 + slot
                if abstract_number > 129:
                    continue
                placements.append((abstract_number, embedded.image.copy()))
    return placements


def extract_abstract_images(pdf_path: Path, terms: list[dict], output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    abstract_terms = {term["abstractIndex"]: term for term in terms if term["abstractIndex"]}
    matched_numbers = set()
    for abstract_number, source_image in match_pdf_images(pdf_path):
        term = abstract_terms[abstract_number]
        filename = f"{abstract_number:03d}-{slugify(term['nameEn'])}.webp"
        destination = output_dir / filename
        rgb = Image.new("RGB", source_image.size, "#0b1120")
        if source_image.mode == "RGBA":
            rgb.paste(source_image, mask=source_image.getchannel("A"))
        else:
            rgb.paste(source_image.convert("RGB"))
        display = ImageOps.fit(rgb, (960, 540), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        display.save(destination, "WEBP", quality=82, method=6)
        term["image"] = {
            "status": "available",
            "path": f"assets/images/abstract/{filename}",
            "altZh": f"{term['nameZh']}的抽象视觉参考",
            "altEn": f"Abstract visual reference for {term['nameEn']}",
        }
        matched_numbers.add(abstract_number)

    for abstract_number, term in abstract_terms.items():
        if abstract_number not in matched_numbers:
            term["image"] = {
                "status": "missing",
                "path": "assets/images/placeholder.svg",
                "altZh": f"{term['nameZh']}图片待补充",
                "altEn": f"Image pending for {term['nameEn']}",
            }

    return matched_numbers


def extract_reference_collages(workbook_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(workbook_path) as archive:
        media = sorted(name for name in archive.namelist() if name.startswith("xl/media/"))
        for idx, name in enumerate(media[:2], start=1):
            destination = output_dir / f"reference-{idx}.png"
            destination.write_bytes(archive.read(name))
            extracted.append(destination)
    if len(extracted) != 2:
        raise RuntimeError("Expected two embedded visual-reference collages in the workbook")
    return extracted


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def create_brand_images(collage_paths: list[Path], assets_dir: Path):
    source_a = Image.open(collage_paths[0]).convert("RGB")
    source_b = Image.open(collage_paths[1]).convert("RGB")
    canvas = Image.new("RGB", (1600, 900), "#07111f")
    left = ImageOps.fit(source_a, (800, 900), method=Image.Resampling.LANCZOS)
    right = ImageOps.fit(source_b, (800, 900), method=Image.Resampling.LANCZOS)
    canvas.paste(left, (0, 0))
    canvas.paste(right, (800, 0))
    canvas = ImageEnhance.Contrast(canvas).enhance(1.06)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(canvas.height):
        alpha = int(30 + 150 * (y / canvas.height))
        draw.line((0, y, canvas.width, y), fill=(3, 9, 20, alpha))
    hero = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    hero.save(assets_dir / "hero.webp", "WEBP", quality=84, method=6)

    preview = ImageOps.fit(hero, (1280, 640), method=Image.Resampling.LANCZOS)
    preview_overlay = Image.new("RGBA", preview.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(preview_overlay)
    draw.rounded_rectangle((54, 70, 1226, 570), radius=28, fill=(4, 12, 27, 205), outline=(88, 199, 255, 150), width=2)
    draw.text((108, 135), "AI 视觉语言库", font=font(64, True), fill="#f8fbff")
    draw.text((108, 230), "AI Visual Language Library", font=font(38, True), fill="#70d9ff")
    draw.text((108, 322), "538 个可搜索视觉词条 · 129 个抽象视觉概念", font=font(29), fill="#d8e8f5")
    draw.text((108, 376), "把模糊想法，变成 AI 能理解的画面描述", font=font(31), fill="#ffffff")
    draw.rounded_rectangle((108, 470, 368, 522), radius=26, fill="#1787a8")
    draw.text((154, 480), "OPEN SOURCE", font=font(23, True), fill="#ffffff")
    preview = Image.alpha_composite(preview.convert("RGBA"), preview_overlay).convert("RGB")
    preview.save(assets_dir / "social-preview.png", "PNG", optimize=True)


def main():
    parser = argparse.ArgumentParser(description="Build the AI Visual Language Library")
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    data_dir = root / "data"
    docs_dir = root / "docs"
    docs_data_dir = docs_dir / "data"
    assets_dir = docs_dir / "assets"
    image_dir = assets_dir / "images" / "abstract"

    for directory in (data_dir, docs_data_dir, assets_dir, image_dir):
        directory.mkdir(parents=True, exist_ok=True)

    terms, templates, mappings = load_workbook_data(args.workbook)
    matched_numbers = extract_abstract_images(args.pdf, terms, image_dir)

    placeholder = assets_dir / "images" / "placeholder.svg"
    placeholder.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" role="img" aria-labelledby="t d">'
        '<title id="t">Image pending</title><desc id="d">Abstract visual reference is awaiting a community contribution.</desc>'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#101b2e"/><stop offset="1" stop-color="#082d42"/></linearGradient></defs>'
        '<rect width="960" height="540" fill="url(#g)"/><circle cx="480" cy="250" r="92" fill="none" stroke="#4fc7ee" stroke-width="2" stroke-dasharray="10 12"/>'
        '<path d="M438 250h84M480 208v84" stroke="#79dcfa" stroke-width="8" stroke-linecap="round"/>'
        '<text x="480" y="386" fill="#d9f4ff" text-anchor="middle" font-family="Arial,sans-serif" font-size="28">IMAGE PENDING · 图片待补充</text></svg>',
        encoding="utf-8",
    )

    term_fields = [
        "id", "module", "moduleSlug", "category", "nameZh", "nameEn", "plainExplanation",
        "promptExample", "commonPairings", "abstractIndex", "imageStatus", "imagePath",
    ]
    csv_terms = []
    for term in terms:
        row = dict(term)
        row["imageStatus"] = term["image"]["status"] if term["image"] else "none"
        row["imagePath"] = term["image"]["path"] if term["image"] else ""
        row.pop("image", None)
        csv_terms.append(row)

    write_json(data_dir / "terms.json", terms)
    write_csv(data_dir / "terms.csv", csv_terms, term_fields)
    write_json(data_dir / "prompt-templates.json", templates)
    write_csv(data_dir / "prompt-templates.csv", templates, ["id", "type", "name", "recommendedStructure", "copyReadyExample", "useCase"])
    write_json(data_dir / "abstract-mappings.json", mappings)
    write_csv(data_dir / "abstract-mappings.csv", mappings, ["id", "concept", "visualCarrier", "coreAction", "plainExplanation", "promptExample", "commonPairings"])

    for filename in ("terms.json", "prompt-templates.json", "abstract-mappings.json"):
        shutil.copy2(data_dir / filename, docs_data_dir / filename)

    collage_paths = extract_reference_collages(args.workbook, assets_dir / "references")
    create_brand_images(collage_paths, assets_dir)

    metadata = {
        "version": "1.0.0",
        "counts": {
            "terms": len(terms),
            "promptTemplates": len(templates),
            "abstractMappings": len(mappings),
            "abstractVisuals": sum(1 for term in terms if term["abstractIndex"]),
            "availableAbstractImages": len(matched_numbers),
            "missingAbstractImages": len(MISSING_ABSTRACT_IMAGES),
        },
        "missingAbstractImageIds": sorted(MISSING_ABSTRACT_IMAGES),
        "sourceFiles": {
            args.workbook.name: {"sha256": sha256(args.workbook), "bytes": args.workbook.stat().st_size},
            args.pdf.name: {"sha256": sha256(args.pdf), "bytes": args.pdf.stat().st_size},
        },
    }
    write_json(data_dir / "metadata.json", metadata)
    shutil.copy2(data_dir / "metadata.json", docs_data_dir / "metadata.json")

    checksums = [
        f"{metadata['sourceFiles'][args.workbook.name]['sha256']}  {args.workbook.name}",
        f"{metadata['sourceFiles'][args.pdf.name]['sha256']}  {args.pdf.name}",
    ]
    (root / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")

    expected = {
        "terms": 538,
        "templates": 41,
        "mappings": 24,
        "abstract": 129,
        "images": 121,
        "missing": MISSING_ABSTRACT_IMAGES,
    }
    actual_missing = {term["abstractIndex"] for term in terms if term["abstractIndex"] and term["image"]["status"] == "missing"}
    assert len(terms) == expected["terms"]
    assert len(templates) == expected["templates"]
    assert len(mappings) == expected["mappings"]
    assert sum(1 for term in terms if term["abstractIndex"]) == expected["abstract"]
    assert len(matched_numbers) == expected["images"]
    assert actual_missing == expected["missing"]
    print(json.dumps(metadata["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
