"""
Week 2 - Task: Text Extraction Pipeline
AI-Based Legal Document Assistant for Small Businesses

Ye script data/ folder ke andar sabhi PDFs (templates, compliance_docs,
sample_contracts) se text extract karke ek clean, structured format mein
save karta hai — jo aage chunking + embeddings ke liye use hoga.

Usage:
    python week2_text_extraction.py
"""

import fitz  # PyMuPDF
import os
import json
from pathlib import Path

# ---------------------------------------------------------
# CONFIG - Apne project ke hisaab se paths adjust karo
# ---------------------------------------------------------
DATA_DIR = Path("data")               # root data folder
OUTPUT_DIR = Path("data/extracted_text")  # yahan extracted text save hoga

SUBFOLDERS = ["templates", "compliance_docs", "sample_contracts"]


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Ek PDF file se saara text nikaalta hai using PyMuPDF (fitz).
    Page-breaks ko clearly mark karta hai taaki baad mein chunking
    ke time page-reference bhi rakh sakein.
    """
    text_parts = []
    try:
        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(f"\n[PAGE {page_num}]\n{page_text.strip()}")
        doc.close()
    except Exception as e:
        print(f"  ERROR reading {pdf_path.name}: {e}")
        return ""

    return "\n".join(text_parts)


def clean_text(raw_text: str) -> str:
    """
    Basic cleaning - extra blank lines, multiple spaces hataata hai.
    Aap yahan aur cleaning rules add kar sakte ho (headers/footers removal, etc.)
    """
    lines = [line.strip() for line in raw_text.split("\n")]
    # Empty consecutive lines ko ek mein convert karo
    cleaned_lines = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                cleaned_lines.append(line)
            prev_blank = True
        else:
            cleaned_lines.append(line)
            prev_blank = False
    return "\n".join(cleaned_lines)


def process_all_documents():
    """
    data/templates, data/compliance_docs, data/sample_contracts - teeno
    folders ke sabhi PDFs process karta hai aur ek JSON file mein save
    karta hai jisme har document ka metadata + extracted text hoga.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_documents = []
    total_files = 0

    for subfolder in SUBFOLDERS:
        folder_path = DATA_DIR / subfolder

        if not folder_path.exists():
            print(f"⚠️  Folder nahi mila: {folder_path} — skip kar raha hoon")
            continue

        pdf_files = sorted(folder_path.glob("*.pdf"))
        print(f"\n📁 {subfolder}/  --  {len(pdf_files)} PDF(s) mile")

        for pdf_file in pdf_files:
            print(f"  → Processing: {pdf_file.name}")

            raw_text = extract_text_from_pdf(pdf_file)
            if not raw_text:
                print(f"    ⚠️  Koi text nahi mila is file mein, skip kar raha hoon")
                continue

            cleaned = clean_text(raw_text)

            doc_record = {
                "filename": pdf_file.name,
                "category": subfolder,          # templates / compliance_docs / sample_contracts
                "source_path": str(pdf_file),
                "char_count": len(cleaned),
                "text": cleaned,
            }
            all_documents.append(doc_record)

            # Har document ka individual .txt file bhi save karo (easy manual inspection ke liye)
            txt_output_path = OUTPUT_DIR / f"{pdf_file.stem}.txt"
            txt_output_path.write_text(cleaned, encoding="utf-8")

            total_files += 1
            print(f"    ✅ Extracted {doc_record['char_count']} characters")

    # Sabhi documents ka combined JSON bhi bana do - RAG pipeline ke liye useful
    combined_json_path = OUTPUT_DIR / "all_documents.json"
    with open(combined_json_path, "w", encoding="utf-8") as f:
        json.dump(all_documents, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"✅ DONE — Total {total_files} documents processed")
    print(f"📄 Individual .txt files: {OUTPUT_DIR}/")
    print(f"📦 Combined JSON: {combined_json_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    process_all_documents()