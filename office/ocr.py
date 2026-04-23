from __future__ import annotations

import io
from pathlib import Path

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes


DEFAULT_LANG = "jpn+jpn_vert"
TESSERACT_CONFIG = "--oem 3 --psm 6"


def _preprocess(img: Image.Image) -> Image.Image:
    # Grayscale helps printed-document OCR and trims memory.
    if img.mode != "L":
        img = img.convert("L")
    return img


def ocr_image_bytes(data: bytes, lang: str = DEFAULT_LANG) -> str:
    img = Image.open(io.BytesIO(data))
    img = _preprocess(img)
    return pytesseract.image_to_string(img, lang=lang, config=TESSERACT_CONFIG).strip()


def ocr_pdf_bytes(data: bytes, lang: str = DEFAULT_LANG, dpi: int = 300) -> str:
    pages = convert_from_bytes(data, dpi=dpi)
    parts: list[str] = []
    for i, img in enumerate(pages, start=1):
        img = _preprocess(img)
        text = pytesseract.image_to_string(img, lang=lang, config=TESSERACT_CONFIG).strip()
        parts.append(f"----- Page {i} -----\n{text}")
    return "\n\n".join(parts)


def ocr_file(filename: str, data: bytes, lang: str = DEFAULT_LANG) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return ocr_pdf_bytes(data, lang=lang)
    return ocr_image_bytes(data, lang=lang)
