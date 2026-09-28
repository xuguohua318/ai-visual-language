from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MISSING = {49, 50, 51, 65, 69, 72, 115, 120}


def fail(message: str):
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main():
    terms = json.loads((ROOT / "data/terms.json").read_text(encoding="utf-8"))
    templates = json.loads((ROOT / "data/prompt-templates.json").read_text(encoding="utf-8"))
    mappings = json.loads((ROOT / "data/abstract-mappings.json").read_text(encoding="utf-8"))
    metadata = json.loads((ROOT / "data/metadata.json").read_text(encoding="utf-8"))

    if len(terms) != 538: fail(f"expected 538 terms, got {len(terms)}")
    if len(templates) != 41: fail(f"expected 41 templates, got {len(templates)}")
    if len(mappings) != 24: fail(f"expected 24 mappings, got {len(mappings)}")
    if len({term["id"] for term in terms}) != 538: fail("term IDs are not unique")
    if [term["id"] for term in terms] != [f"AVL-{i:04d}" for i in range(1, 539)]: fail("term IDs are not stable and sequential")

    required = ["module", "category", "nameZh", "nameEn", "plainExplanation", "promptExample", "commonPairings"]
    for term in terms:
        for field in required:
            if not term.get(field): fail(f"{term['id']} missing {field}")

    abstract = [term for term in terms if term["abstractIndex"]]
    if len(abstract) != 129: fail(f"expected 129 abstract terms, got {len(abstract)}")
    if [term["abstractIndex"] for term in abstract] != list(range(1, 130)): fail("abstract indexes are not sequential")
    missing = {term["abstractIndex"] for term in abstract if term["image"]["status"] == "missing"}
    if missing != EXPECTED_MISSING: fail(f"unexpected missing image set: {sorted(missing)}")

    images = [term for term in abstract if term["image"]["status"] == "available"]
    if len(images) != 121: fail(f"expected 121 images, got {len(images)}")
    for term in images:
        path = ROOT / "docs" / term["image"]["path"]
        if not path.exists() or path.stat().st_size < 2_500: fail(f"invalid image for {term['id']}: {path}")

    with (ROOT / "data/terms.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 538: fail("CSV row count mismatch")

    for name in ("terms.json", "prompt-templates.json", "abstract-mappings.json", "metadata.json"):
        if (ROOT / "data" / name).read_bytes() != (ROOT / "docs/data" / name).read_bytes(): fail(f"docs copy differs: {name}")

    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    if "__OWNER__" not in html and not re.search(r"github\.com/[A-Za-z0-9-]+/ai-visual-language", html): fail("GitHub owner URL missing")
    if metadata["counts"]["terms"] != 538: fail("metadata counts mismatch")

    ignored_parts = {".git", ".edge-test", "release-assets", "__pycache__"}
    large_files = []
    for current, directories, filenames in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in ignored_parts]
        for filename in filenames:
            path = Path(current) / filename
            if path.stat().st_size >= 100 * 1024 * 1024:
                large_files.append(path)
    if large_files: fail("files >=100 MiB found: " + ", ".join(map(str, large_files)))
    print("PASS: 538 terms, 41 templates, 24 mappings, 121 images, 8 placeholders")


if __name__ == "__main__":
    main()
