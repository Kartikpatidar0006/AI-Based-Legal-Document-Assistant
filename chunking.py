"""
Week 3 - Stage 1: Document Chunking
AI-Based Legal Document Assistant for Small Businesses

This script reads the combined JSON of all extracted documents
(data/extracted_text/all_documents.json), splits each document's text
into overlapping chunks using LangChain's RecursiveCharacterTextSplitter,
preserves per-chunk metadata (filename, category, chunk_index, source_path),
and saves the result to data/chunks/all_chunks.json.

Usage:
    python chunking.py

Dependencies:
    pip install langchain langchain-text-splitters
"""

import json
import sys
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

from langchain_text_splitters import RecursiveCharacterTextSplitter

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
INPUT_JSON: Path = Path("data/extracted_text/all_documents.json")
OUTPUT_DIR: Path = Path("data/chunks")
OUTPUT_JSON: Path = OUTPUT_DIR / "all_chunks.json"

CHUNK_SIZE: int = 700        # target characters per chunk
CHUNK_OVERLAP: int = 100     # overlap between consecutive chunks


def load_documents(json_path: Path) -> list[dict]:
    """
    Load the list of extracted document records from the combined JSON file.
    Each record has: filename, category, source_path, char_count, text.
    """
    if not json_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {json_path}\n"
            "Please run week2_text_extraction.py first to generate all_documents.json."
        )

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            documents = json.load(f)
        print(f"✅ Loaded {len(documents)} document(s) from {json_path}")
        return documents
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from {json_path}: {e}")


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Split every document's text into overlapping chunks using
    RecursiveCharacterTextSplitter.

    Returns a flat list of chunk records, each containing:
        chunk_id     – unique identifier  (filename__chunkN)
        text         – the chunk text
        filename     – source PDF filename
        category     – templates / compliance_docs / sample_contracts
        chunk_index  – 0-based position of this chunk in its document
        source_path  – original file path (for traceability)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Prefer splitting at paragraph, then sentence, then word boundaries
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    all_chunks: list[dict] = []

    for doc in documents:
        filename: str = doc.get("filename", "unknown")
        category: str = doc.get("category", "unknown")
        source_path: str = doc.get("source_path", "")
        text: str = doc.get("text", "")

        if not text.strip():
            print(f"  ⚠️  Skipping '{filename}' — empty text")
            continue

        # Split the raw text into chunk strings
        raw_chunks: list[str] = splitter.split_text(text)

        for idx, chunk_text in enumerate(raw_chunks):
            # Build a human-readable unique ID for each chunk
            stem = Path(filename).stem  # strip .pdf extension
            chunk_id = f"{stem}__chunk{idx}"

            all_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "filename": filename,
                    "category": category,
                    "chunk_index": idx,
                    "source_path": source_path,
                }
            )

    return all_chunks


def save_chunks(chunks: list[dict], output_path: Path) -> None:
    """
    Persist the list of chunk records to a JSON file.
    Creates the output directory if it doesn't exist.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(chunks)} chunks → {output_path}")
    except IOError as e:
        raise IOError(f"Failed to write chunks to {output_path}: {e}")


def print_summary(chunks: list[dict]) -> None:
    """
    Print a human-readable summary of the chunking results.
    """
    if not chunks:
        print("⚠️  No chunks were generated.")
        return

    total = len(chunks)
    avg_size = sum(len(c["text"]) for c in chunks) / total

    # Count chunks per category
    category_counts: dict[str, int] = {}
    for chunk in chunks:
        cat = chunk["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print("\n" + "=" * 55)
    print("  CHUNKING SUMMARY")
    print("=" * 55)
    print(f"  Total chunks created  : {total}")
    print(f"  Average chunk size    : {avg_size:.0f} characters")
    print(f"  Chunk size target     : {CHUNK_SIZE} chars  |  Overlap: {CHUNK_OVERLAP} chars")
    print("\n  Chunks per category:")
    for cat, count in sorted(category_counts.items()):
        print(f"    • {cat:<25} {count:>4} chunks")
    print("=" * 55)


def main() -> None:
    print("=" * 55)
    print("  STAGE 1 — DOCUMENT CHUNKING")
    print("=" * 55)

    # Step 1: Load documents
    try:
        documents = load_documents(INPUT_JSON)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ ERROR: {e}")
        return

    # Step 2: Chunk every document
    print(f"\n🔪 Splitting documents into chunks  (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})...")
    chunks = chunk_documents(documents)

    if not chunks:
        print("❌ No chunks were generated. Please check your input data.")
        return

    # Step 3: Save to JSON
    try:
        save_chunks(chunks, OUTPUT_JSON)
    except IOError as e:
        print(f"\n❌ ERROR: {e}")
        return

    # Step 4: Print summary
    print_summary(chunks)
    print(f"\n✅ Done! Next step: run  python embed_and_store.py")


if __name__ == "__main__":
    main()
