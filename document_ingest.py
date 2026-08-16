"""
document_ingest.py
AI-Based Legal Document Assistant for Small Businesses
Week 5+ Extension: Multi-Format Document Ingestion (PDF + DOCX + Images/OCR)

─────────────────────────────────────────────────────────────────
WHERE THIS FITS IN THE OVERALL PIPELINE
─────────────────────────────────────────────────────────────────

  [OLD] Week 2 → week2_text_extraction.py
                 PDFs only → plain text → all_documents.json

  [NEW] This file (document_ingest.py) REPLACES week2_text_extraction.py
        Supports: .pdf  .docx  .jpg  .jpeg  .png  .tiff  .bmp
        Output:   same all_documents.json that chunking.py already reads
                  (backward-compatible — no changes needed in chunking.py)

  Week 3 → chunking.py        text → overlapping chunks (unchanged)
         → embed_and_store.py  chunks → 384-dim vectors → ChromaDB (unchanged)
  Week 4 → rag_pipeline.py    RAG generation via Gemini API (unchanged)

─────────────────────────────────────────────────────────────────
EXTRACTION METHODS
─────────────────────────────────────────────────────────────────

  PDF  → PyMuPDF (fitz) primary
         If extracted text < MIN_TEXT_CHARS, PDF is likely a scanned image:
         falls back to Tesseract OCR on page pixmaps automatically.

  DOCX → python-docx  (paragraphs + table cells, in document order)

  IMAGE→ pytesseract + Pillow
         Preprocessing: grayscale → Otsu threshold → OCR
         Confidence check: if avg word confidence < OCR_CONFIDENCE_THRESHOLD
         a warning is added so the user knows to verify the text.

─────────────────────────────────────────────────────────────────
HOW TO RUN
─────────────────────────────────────────────────────────────────

  Single file:
      python document_ingest.py --file path/to/document.pdf
      python document_ingest.py --file path/to/contract.docx
      python document_ingest.py --file path/to/scan.jpg

  Batch folder (replaces week2_text_extraction.py):
      python document_ingest.py --folder data/templates
      python document_ingest.py --folder data/uploads --output data/extracted_text

─────────────────────────────────────────────────────────────────
SYSTEM REQUIREMENTS
─────────────────────────────────────────────────────────────────

  pip install pymupdf python-docx pytesseract Pillow

  Tesseract OCR binary (required for image/OCR paths):
      Windows: https://github.com/UB-Mannheim/tesseract/wiki
               Install tesseract-ocr-w64-setup-*.exe
               Default path: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
               Set TESSERACT_CMD below OR set env var TESSERACT_CMD.

─────────────────────────────────────────────────────────────────
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Output directory — where all_documents.json and individual .txt files go
DEFAULT_OUTPUT_DIR: Path = Path("data/extracted_text")

# Supported file extensions per extraction method
PDF_EXTENSIONS:   frozenset[str] = frozenset({".pdf"})
DOCX_EXTENSIONS:  frozenset[str] = frozenset({".docx"})
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".tiff", ".bmp"})

ALL_SUPPORTED: frozenset[str] = PDF_EXTENSIONS | DOCX_EXTENSIONS | IMAGE_EXTENSIONS

# If a PDF yields fewer characters than this, assume it is a scanned/image PDF
# and fall back to OCR automatically
MIN_TEXT_CHARS: int = 50

# Average Tesseract per-word confidence (0–100) below which we warn the user
OCR_CONFIDENCE_THRESHOLD: int = 60

# Path to Tesseract binary on Windows — override via env var TESSERACT_CMD
# or change this constant if your install location differs.
TESSERACT_CMD: str = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

# Data-folder subfolders treated as category names (mirrors week2 logic)
CATEGORY_SUBFOLDERS: list[str] = ["templates", "compliance_docs", "sample_contracts"]


# ─────────────────────────────────────────────────────────────────────────────
# TEXT CLEANING  (mirrors week2_text_extraction.py's clean_text)
# ─────────────────────────────────────────────────────────────────────────────

def clean_text(raw_text: str) -> str:
    """
    Normalise whitespace in extracted text:
    - Strip leading/trailing space from each line
    - Collapse consecutive blank lines into a single blank line
    Returns the cleaned string.
    """
    lines = [line.strip() for line in raw_text.split("\n")]

    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                cleaned.append(line)
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    return "\n".join(cleaned)


# ─────────────────────────────────────────────────────────────────────────────
# OCR HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _configure_tesseract() -> None:
    """
    Point pytesseract at the Tesseract binary.
    Called once before any OCR work. Safe to call multiple times.
    """
    import pytesseract  # local import — only needed on OCR paths

    if Path(TESSERACT_CMD).exists():
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    # If the binary is already on PATH (Linux/macOS CI) we leave it as-is.


def _ocr_image(pil_image) -> tuple[str, float]:
    """
    Run Tesseract OCR on a PIL Image.

    Preprocessing steps applied before OCR:
      1. Convert to grayscale — colour information is irrelevant for text.
      2. Apply Otsu adaptive threshold → pure black-and-white bitmap.
         This removes noise from scanned pages, shadows, and uneven lighting,
         which substantially improves Tesseract's character recognition.

    Returns:
        text       – extracted string (may be empty for blank pages)
        avg_conf   – average per-word confidence (0.0–100.0)
                     -1.0 signals that no words were detected at all.
    """
    import pytesseract
    from PIL import Image, ImageFilter

    # ── Step 1: Grayscale ────────────────────────────────────────────────────
    gray = pil_image.convert("L")

    # ── Step 2: Otsu binarisation via point threshold ────────────────────────
    # Pillow does not have a direct Otsu method, so we use a simple approach:
    # compute a histogram-based threshold and apply it with point().
    histogram = gray.histogram()
    total_pixels = gray.width * gray.height

    # Iteratively find threshold that minimises intra-class variance (Otsu)
    sum_all = sum(i * histogram[i] for i in range(256))
    sum_bg = 0
    weight_bg = 0
    max_variance = 0.0
    threshold = 127  # sensible fallback

    for t in range(256):
        weight_bg += histogram[t]
        if weight_bg == 0:
            continue
        weight_fg = total_pixels - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * histogram[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = t

    binarised = gray.point(lambda p: 255 if p >= threshold else 0)

    # ── OCR pass 1: get the plain text ───────────────────────────────────────
    text: str = pytesseract.image_to_string(binarised, lang="eng")

    # ── OCR pass 2: get per-word confidence for quality check ────────────────
    data = pytesseract.image_to_data(
        binarised, lang="eng", output_type=pytesseract.Output.DICT
    )
    confidences = [
        int(c)
        for c in data.get("conf", [])
        if str(c).strip().lstrip("-").isdigit() and int(c) >= 0
    ]
    avg_conf = sum(confidences) / len(confidences) if confidences else -1.0

    return text, avg_conf


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION METHODS
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf(file_path: Path) -> tuple[str, str, list[str]]:
    """
    Extract text from a PDF file.

    Strategy:
      1. Try PyMuPDF — fast, native text layer extraction.
      2. If the total extracted text is shorter than MIN_TEXT_CHARS, the PDF
         is almost certainly a scanned image with no embedded text layer.
         Fall back to OCR: render each page to a pixmap image and run
         Tesseract on each rendered page image.

    Returns:
        text              – cleaned extracted text
        extraction_method – "pymupdf" or "ocr-tesseract"
        warnings          – list of warning strings (may be empty)
    """
    import fitz  # PyMuPDF

    warnings: list[str] = []
    text_parts: list[str] = []

    # ── Primary: PyMuPDF native text layer ───────────────────────────────────
    try:
        doc = fitz.open(str(file_path))
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(f"\n[PAGE {page_num}]\n{page_text.strip()}")
        doc.close()
    except Exception as exc:
        warnings.append(f"PyMuPDF read error: {exc}")
        text_parts = []

    raw_text = "\n".join(text_parts)

    # ── Check if we actually got meaningful text ──────────────────────────────
    if len(raw_text.strip()) >= MIN_TEXT_CHARS:
        return clean_text(raw_text), "pymupdf", warnings

    # ── Fallback: OCR via page pixmaps ───────────────────────────────────────
    # The PDF has no embedded text (scanned/image-only PDF).
    # We render every page to a pixel image and pass it to Tesseract.
    warnings.append("scanned PDF - used OCR fallback")
    _configure_tesseract()

    try:
        from PIL import Image
        import io

        doc = fitz.open(str(file_path))
        ocr_parts: list[str] = []
        all_confidences: list[float] = []

        for page_num, page in enumerate(doc, start=1):
            # Render at 2× resolution for better OCR accuracy on small fonts
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)

            # Convert pixmap bytes to a PIL Image (RGB mode)
            img_bytes = pix.tobytes("png")
            pil_img = Image.open(io.BytesIO(img_bytes))

            page_text, avg_conf = _ocr_image(pil_img)

            if page_text.strip():
                ocr_parts.append(f"\n[PAGE {page_num}]\n{page_text.strip()}")
            if avg_conf >= 0:
                all_confidences.append(avg_conf)

        doc.close()

        # Overall confidence check
        if all_confidences:
            overall_conf = sum(all_confidences) / len(all_confidences)
            if overall_conf < OCR_CONFIDENCE_THRESHOLD:
                warnings.append(
                    f"low OCR confidence ({overall_conf:.1f}%) - please verify extracted text"
                )

        ocr_text = clean_text("\n".join(ocr_parts))
        return ocr_text, "ocr-tesseract", warnings

    except Exception as exc:
        warnings.append(f"OCR fallback failed: {exc}")
        return "", "ocr-tesseract", warnings


def _extract_docx(file_path: Path) -> tuple[str, str, list[str]]:
    """
    Extract text from a .docx Word document.

    Extracts:
      - All paragraph text (in document order)
      - All table cell text (row by row, cell by cell)
        Many contracts use tables for clause numbering and signature blocks;
        skipping tables would silently lose important terms.

    Returns:
        text              – cleaned extracted text
        extraction_method – "python-docx"
        warnings          – list of warning strings
    """
    import docx  # python-docx

    warnings: list[str] = []
    parts: list[str] = []

    try:
        document = docx.Document(str(file_path))

        # python-docx exposes the document body as an XML element; iterating
        # document.element.body gives us paragraphs and tables in order.
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
        from docx.table import Table

        for child in document.element.body:
            # Paragraph
            if child.tag == qn("w:p"):
                para = Paragraph(child, document)
                para_text = para.text.strip()
                if para_text:
                    parts.append(para_text)

            # Table — extract all cell text row by row
            elif child.tag == qn("w:tbl"):
                tbl = Table(child, document)
                for row in tbl.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        parts.append("  |  ".join(row_cells))

    except Exception as exc:
        warnings.append(f"python-docx read error: {exc}")
        return "", "python-docx", warnings

    raw_text = "\n".join(parts)

    if not raw_text.strip():
        warnings.append("no text found in DOCX - document may be empty or image-only")

    return clean_text(raw_text), "python-docx", warnings


def _extract_image(file_path: Path) -> tuple[str, str, list[str]]:
    """
    Extract text from an image file (jpg, jpeg, png, tiff, bmp) via OCR.

    Applies grayscale + Otsu binarisation preprocessing before running
    Tesseract — this reliably improves recognition on photos of printed
    pages, scanned contracts, and smartphone captures.

    Returns:
        text              – cleaned extracted text
        extraction_method – "ocr-tesseract"
        warnings          – list of warning strings
    """
    from PIL import Image

    warnings: list[str] = []
    _configure_tesseract()

    try:
        pil_img = Image.open(str(file_path))
        text, avg_conf = _ocr_image(pil_img)
    except Exception as exc:
        warnings.append(f"image OCR error: {exc}")
        return "", "ocr-tesseract", warnings

    if not text.strip():
        warnings.append("no text found in image - OCR returned empty result")
    elif avg_conf >= 0 and avg_conf < OCR_CONFIDENCE_THRESHOLD:
        warnings.append(
            f"low OCR confidence ({avg_conf:.1f}%) - please verify extracted text"
        )

    return clean_text(text), "ocr-tesseract", warnings


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(file_path: Path) -> dict:
    """
    Universal single-file entry-point.

    Detects file type from extension, routes to the correct extractor,
    and always returns the same dict structure regardless of source format.

    The dict is backward-compatible with all_documents.json consumed by
    chunking.py — the mandatory fields (filename, category, source_path,
    char_count, text) are always present. New fields (file_type,
    extraction_method, warnings) are additive and ignored by chunking.py.

    Args:
        file_path: Path to the document file (PDF, DOCX, or image).

    Returns:
        {
            "filename":          str,   # e.g. "contract.pdf"
            "file_type":         str,   # "pdf" | "docx" | "image"
            "category":          str,   # inferred from parent folder name, or "unknown"
            "source_path":       str,   # absolute path string
            "char_count":        int,   # length of extracted text
            "text":              str,   # the full extracted + cleaned text
            "extraction_method": str,   # "pymupdf" | "python-docx" | "ocr-tesseract"
            "warnings":          list[str]  # empty list if all went well
        }
    """
    file_path = Path(file_path).resolve()
    suffix = file_path.suffix.lower()
    warnings: list[str] = []

    # ── Infer category from parent folder name (mirrors week2 logic) ──────────
    parent_name = file_path.parent.name
    category = parent_name if parent_name in CATEGORY_SUBFOLDERS else "unknown"

    # ── Route to correct extractor ────────────────────────────────────────────
    if suffix in PDF_EXTENSIONS:
        file_type = "pdf"
        text, method, extra_warnings = _extract_pdf(file_path)

    elif suffix in DOCX_EXTENSIONS:
        file_type = "docx"
        text, method, extra_warnings = _extract_docx(file_path)

    elif suffix in IMAGE_EXTENSIONS:
        file_type = "image"
        text, method, extra_warnings = _extract_image(file_path)

    else:
        # Unsupported format — return gracefully rather than crashing
        return {
            "filename":          file_path.name,
            "file_type":         suffix.lstrip(".") or "unknown",
            "category":          category,
            "source_path":       str(file_path),
            "char_count":        0,
            "text":              "",
            "extraction_method": "none",
            "warnings":          [f"unsupported file format: '{suffix}'"],
        }

    warnings.extend(extra_warnings)

    return {
        "filename":          file_path.name,
        "file_type":         file_type,
        "category":          category,
        "source_path":       str(file_path),
        "char_count":        len(text),
        "text":              text,
        "extraction_method": method,
        "warnings":          warnings,
    }


def process_folder(
    folder_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    save_individual_txt: bool = True,
) -> list[dict]:
    """
    Batch-process all supported files in a folder.

    Scans folder_path (non-recursively) for any file with a supported
    extension, calls extract_text() on each, and writes:
      - data/extracted_text/all_documents.json  ← the combined list
      - data/extracted_text/<stem>.txt           ← per-file text (optional)

    The JSON structure matches exactly what chunking.py already reads,
    so this function is a drop-in replacement for
    week2_text_extraction.py's process_all_documents().

    Args:
        folder_path:          Directory to scan.
        output_dir:           Where to write all_documents.json and .txt files.
        save_individual_txt:  If True, also save a .txt file per document.

    Returns:
        List of result dicts (one per successfully found file).
    """
    folder_path = Path(folder_path)
    output_dir = Path(output_dir)

    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all supported files (sorted for deterministic order)
    files = sorted(
        f for f in folder_path.iterdir()
        if f.is_file() and f.suffix.lower() in ALL_SUPPORTED
    )

    if not files:
        print(f"  ⚠️  No supported files found in: {folder_path}")
        return []

    print(f"\n📁 {folder_path.name}/  —  {len(files)} file(s) found")

    results: list[dict] = []

    for file_path in files:
        print(f"  → Processing: {file_path.name} ...", end=" ")
        result = extract_text(file_path)

        if result["warnings"]:
            print(f"⚠️  {len(result['warnings'])} warning(s)")
            for w in result["warnings"]:
                print(f"      • {w}")
        else:
            print(f"✅  {result['char_count']} chars  [{result['extraction_method']}]")

        results.append(result)

        # Individual .txt file for easy manual inspection
        if save_individual_txt and result["text"]:
            stem = file_path.stem
            txt_path = output_dir / f"{stem}.txt"
            txt_path.write_text(result["text"], encoding="utf-8")

    # Save combined JSON (what chunking.py reads)
    combined_json_path = output_dir / "all_documents.json"
    with open(combined_json_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    print(f"\n💾 Saved {len(results)} record(s) → {combined_json_path}")
    return results


def process_data_folder(
    data_root: Path = Path("data"),
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[dict]:
    """
    Convenience wrapper that mirrors week2_text_extraction.py's behaviour:
    scans data/templates/, data/compliance_docs/, data/sample_contracts/
    (or any subfolders found), collects ALL supported documents across all
    categories, and writes a single combined all_documents.json.

    Use this when you want to replace the old week2 script entirely.

    Args:
        data_root:  Root data directory containing category subfolders.
        output_dir: Destination for all_documents.json and .txt files.

    Returns:
        Combined list of result dicts from all category folders.
    """
    data_root = Path(data_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Discover subfolders — use the configured list first, then fall back to
    # any subdirectory that exists (to handle custom folder names)
    all_results: list[dict] = []
    total_files = 0

    checked_folders = [
        data_root / cat for cat in CATEGORY_SUBFOLDERS
        if (data_root / cat).exists()
    ]

    if not checked_folders:
        # Fallback: process any subfolders that exist
        checked_folders = [p for p in data_root.iterdir() if p.is_dir()]

    for folder in checked_folders:
        folder_results = process_folder(folder, output_dir=output_dir, save_individual_txt=True)
        all_results.extend(folder_results)
        total_files += len(folder_results)

    # Re-save the combined JSON with all categories together
    combined_json_path = output_dir / "all_documents.json"
    with open(combined_json_path, "w", encoding="utf-8") as fh:
        json.dump(all_results, fh, indent=2, ensure_ascii=False)

    print(f"\n{'='*55}")
    print(f"  INGESTION COMPLETE")
    print(f"{'='*55}")
    print(f"  Total files processed : {total_files}")
    print(f"  Combined JSON         : {combined_json_path}")
    print(f"  Next step             : python chunking.py")
    print(f"{'='*55}")

    return all_results


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY / QUALITY CONTROL TABLE  (for demo / presentation)
# ─────────────────────────────────────────────────────────────────────────────

def summarize_ingestion(results: list[dict]) -> None:
    """
    Print a formatted quality-control table after a batch ingestion run.

    Columns: Filename | Type | Method | Chars | Warnings
    This makes it immediately visible to evaluators that the system tracks
    extraction confidence per document — not just blindly ingesting everything.

    Args:
        results: List of result dicts returned by process_folder() or extract_text().
    """
    if not results:
        print("⚠️  No results to summarise.")
        return

    # Column widths
    W_FILE   = max(len(r["filename"]) for r in results) + 2
    W_FILE   = max(W_FILE, 20)
    W_TYPE   = 7
    W_METHOD = 16
    W_CHARS  = 8
    W_WARN   = 6

    header = (
        f"{'Filename':<{W_FILE}}"
        f"{'Type':<{W_TYPE}}"
        f"{'Method':<{W_METHOD}}"
        f"{'Chars':>{W_CHARS}}"
        f"  {'Warn?':<{W_WARN}}"
        f"  Warning Detail"
    )
    divider = "─" * (len(header) + 20)

    print("\n" + divider)
    print("  INGESTION QUALITY CONTROL SUMMARY")
    print(divider)
    print("  " + header)
    print("  " + "─" * len(header))

    ocr_count       = 0
    low_conf_count  = 0
    error_count     = 0

    for r in results:
        filename  = r["filename"]
        ftype     = r.get("file_type", "?")
        method    = r.get("extraction_method", "?")
        chars     = r.get("char_count", 0)
        warnings  = r.get("warnings", [])

        has_warn  = "⚠️ YES" if warnings else "   no"
        warn_str  = "; ".join(warnings) if warnings else ""

        # Truncate long warning strings for the table
        if len(warn_str) > 60:
            warn_str = warn_str[:57] + "..."

        row = (
            f"{filename:<{W_FILE}}"
            f"{ftype:<{W_TYPE}}"
            f"{method:<{W_METHOD}}"
            f"{chars:>{W_CHARS}}"
            f"  {has_warn:<{W_WARN}}"
            f"  {warn_str}"
        )
        print("  " + row)

        # Aggregate stats
        if method == "ocr-tesseract":
            ocr_count += 1
        if any("low OCR confidence" in w for w in warnings):
            low_conf_count += 1
        if any("error" in w.lower() or "failed" in w.lower() for w in warnings):
            error_count += 1

    print(divider)
    print(f"  Total            : {len(results)} file(s)")
    print(f"  Used OCR         : {ocr_count}  (image files + scanned PDFs)")
    print(f"  Low confidence   : {low_conf_count}  (verify these manually)")
    print(f"  Errors           : {error_count}  (check warnings above)")
    print(divider + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Multi-format document ingestion — "
            "PDF / DOCX / Image (OCR) → all_documents.json"
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--file",
        type=Path,
        metavar="PATH",
        help="Extract text from a single file and pretty-print the result dict.",
    )
    mode.add_argument(
        "--folder",
        type=Path,
        metavar="PATH",
        help=(
            "Batch-process all supported files in a folder. "
            "Use 'data' to replicate week2_text_extraction.py behaviour "
            "(processes templates/, compliance_docs/, sample_contracts/ sub-folders)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory for all_documents.json (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="Skip saving individual .txt files (only write all_documents.json).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("=" * 60)
    print("  MULTI-FORMAT DOCUMENT INGESTION")
    print("=" * 60)

    # ── Single-file mode ──────────────────────────────────────────────────────
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"\n❌ File not found: {file_path}")
            sys.exit(1)

        print(f"\n📄 Extracting: {file_path.name}")
        result = extract_text(file_path)

        print("\n" + "─" * 60)
        print("RESULT DICT:")
        print("─" * 60)
        for key, value in result.items():
            if key == "text":
                # Print only a preview of the text
                preview = value[:500].replace("\n", " ↵ ") + ("..." if len(value) > 500 else "")
                print(f"  text           : {preview}")
            else:
                print(f"  {key:<18}: {value}")
        print("─" * 60)
        return

    # ── Folder batch mode ─────────────────────────────────────────────────────
    folder_path = Path(args.folder)
    output_dir  = Path(args.output)

    if not folder_path.exists():
        print(f"\n❌ Folder not found: {folder_path}")
        sys.exit(1)

    # If the folder is named "data" (the root), use process_data_folder
    # which recursively handles all category sub-folders
    if folder_path.resolve() == Path("data").resolve() or folder_path.name == "data":
        results = process_data_folder(data_root=folder_path, output_dir=output_dir)
    else:
        results = process_folder(
            folder_path,
            output_dir=output_dir,
            save_individual_txt=not args.no_txt,
        )

    # Print quality-control table
    summarize_ingestion(results)


if __name__ == "__main__":
    main()
