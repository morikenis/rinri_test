from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes


NDL_OCR_SRC = os.environ.get("NDL_OCR_SRC", "/opt/ndlocr-lite/src")

DEFAULT_TESSERACT_LANG = "jpn+jpn_vert"
TESSERACT_CONFIG = "--oem 3 --psm 6"

Engine = Literal["ndl", "tesseract"]


# =============================================================================
# Tesseract backend (fallback)
# =============================================================================

def _preprocess_for_tesseract(img: Image.Image) -> Image.Image:
    if img.mode != "L":
        img = img.convert("L")
    return img


def _ocr_image_tesseract(img: Image.Image, lang: str = DEFAULT_TESSERACT_LANG) -> str:
    return pytesseract.image_to_string(
        _preprocess_for_tesseract(img), lang=lang, config=TESSERACT_CONFIG
    ).strip()


# =============================================================================
# NDLOCR-Lite backend
# =============================================================================
# NDLOCR-Lite CLI: python3 ocr.py --sourceimg <img> --output <dir> --json-only
# Output: <dir>/<image_stem>/<image_stem>.json (and xml unless --json-only)
# The exact JSON schema may evolve; we walk the structure to collect readable
# text rather than relying on a specific key path.

_TEXT_KEYS = ("text", "contents", "transcription", "string", "char_list_text", "value")
_LIST_KEYS = (
    "blocks",
    "lines",
    "paragraphs",
    "contents",
    "items",
    "pages",
    "page",
    "children",
    "elements",
    "regions",
    "text_lines",
)


def _collect_text(obj, parts: list[str]) -> None:
    if isinstance(obj, dict):
        for key in _TEXT_KEYS:
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(v)
                break  # avoid double-counting same item
        for key in _LIST_KEYS:
            v = obj.get(key)
            if isinstance(v, list):
                for x in v:
                    _collect_text(x, parts)
        # Fallback: if no known keys present, recurse into all dict values
        if not any(k in obj for k in (*_TEXT_KEYS, *_LIST_KEYS)):
            for v in obj.values():
                _collect_text(v, parts)
    elif isinstance(obj, list):
        for x in obj:
            _collect_text(x, parts)


def _extract_text_from_ndl_json(obj) -> str:
    parts: list[str] = []
    _collect_text(obj, parts)
    return "\n".join(p.strip() for p in parts if p.strip())


def _ocr_image_file_ndl(image_path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        out_dir.mkdir()
        cmd = [
            "python3",
            str(Path(NDL_OCR_SRC) / "ocr.py"),
            "--sourceimg",
            str(image_path),
            "--output",
            str(out_dir),
            "--json-only",
            "--enable-tcy",
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                cwd=NDL_OCR_SRC,
                timeout=600,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"NDLOCR-Lite failed (exit {e.returncode}):\n"
                f"stderr: {e.stderr[-800:] if e.stderr else ''}"
            ) from e

        json_files = sorted(out_dir.rglob("*.json"))
        if not json_files:
            return ""
        texts: list[str] = []
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            texts.append(_extract_text_from_ndl_json(data))
        return "\n\n".join(t for t in texts if t.strip())


def _save_image_as_png(img: Image.Image, path: Path) -> None:
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(path, format="PNG")


def _ocr_image_obj_ndl(img: Image.Image) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.png"
        _save_image_as_png(img, in_path)
        return _ocr_image_file_ndl(in_path)


# =============================================================================
# Public API
# =============================================================================

def ocr_image_bytes(data: bytes, engine: Engine = "ndl") -> str:
    img = Image.open(io.BytesIO(data))
    if engine == "ndl":
        return _ocr_image_obj_ndl(img)
    return _ocr_image_tesseract(img)


def ocr_pdf_bytes(data: bytes, engine: Engine = "ndl", dpi: int = 300) -> str:
    pages = convert_from_bytes(data, dpi=dpi)
    parts: list[str] = []
    for i, img in enumerate(pages, start=1):
        if engine == "ndl":
            text = _ocr_image_obj_ndl(img)
        else:
            text = _ocr_image_tesseract(img)
        parts.append(f"----- Page {i} -----\n{text.strip()}")
    return "\n\n".join(parts)


def ocr_file(filename: str, data: bytes, engine: Engine = "ndl") -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return ocr_pdf_bytes(data, engine=engine)
    return ocr_image_bytes(data, engine=engine)
