"""CLI entry for the preprocessing pipeline.

Usage (inside the api container):
    python -m preprocess.run \
        --input /srv/data/books \
        --output /srv/data/cleaned

Defaults to --input data/books, --output data/cleaned (relative to CWD).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ingest.loader import _read_text  # encoding-aware reader
from preprocess.cleaner import clean_text
from preprocess.metadata import extract_metadata
from preprocess.splitter import find_chapter_headings, split_into_chapters
from preprocess.writer import sanitize_filename, write_chapter


def _log(msg: str) -> None:
    print(msg, flush=True)


def process_one(
    input_path: Path,
    out_root: Path,
    *,
    use_llm_fallback: bool,
) -> int:
    """Process a single source file. Returns the number of chapter files written."""
    raw = _read_text(input_path)
    if not raw.strip():
        _log(f"  skip(empty): {input_path.name}")
        return 0

    cleaned = clean_text(raw)
    meta = extract_metadata(cleaned, source_file=input_path.name)

    headings = find_chapter_headings(cleaned, use_llm_fallback=use_llm_fallback)
    chapters = split_into_chapters(cleaned, headings)

    if len(chapters) == 1 and chapters[0].title == "本文":
        _log(
            f"  warn: no chapter boundaries detected -> writing as single chapter: "
            f"{input_path.name}"
        )

    written = 0
    for ch in chapters:
        write_chapter(out_root, meta, ch)
        written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Preprocess raw book .txt files.")
    parser.add_argument("--input", default="data/books", help="raw book directory")
    parser.add_argument("--output", default="data/cleaned", help="output directory")
    parser.add_argument(
        "--no-llm-fallback",
        action="store_true",
        help="disable LLM-assisted chapter pattern detection",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reprocess even if output for the book already exists",
    )
    args = parser.parse_args()

    in_root = Path(args.input).resolve()
    out_root = Path(args.output).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    files = sorted(in_root.rglob("*.txt"))
    if not files:
        _log(f"no .txt files under {in_root}")
        return 1

    total_books = 0
    total_chapters = 0
    skipped = 0

    for i, path in enumerate(files, start=1):
        # Quick skip: if output dir for this book stem already has files, skip.
        # The actual book dir name is determined later from metadata; we use
        # a conservative check on the source filename stem to avoid LLM calls
        # when nothing has changed.
        if not args.force:
            candidate_dir = out_root / sanitize_filename(path.stem)
            if candidate_dir.exists() and any(candidate_dir.glob("*.txt")):
                _log(f"[{i}/{len(files)}] skip(exists): {path.name}")
                skipped += 1
                continue

        _log(f"[{i}/{len(files)}] processing: {path.name}")
        t0 = time.time()
        try:
            n = process_one(
                path,
                out_root,
                use_llm_fallback=not args.no_llm_fallback,
            )
        except Exception as e:  # noqa: BLE001
            _log(f"  error: {type(e).__name__}: {e}")
            continue
        dt = time.time() - t0
        _log(f"  -> {n} chapter file(s), {dt:.1f}s")
        total_books += 1
        total_chapters += n

    _log("")
    _log(
        f"done. processed: {total_books} book(s), wrote: {total_chapters} chapter(s), "
        f"skipped: {skipped}"
    )
    _log(f"output: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
