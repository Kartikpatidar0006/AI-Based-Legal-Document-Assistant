"""
document_processor.py
AI-Based Legal Document Assistant for Small Businesses
Objective 2: Automated Document Processing — Summarization, Clause Extraction, Risk Detection

─────────────────────────────────────────────────────────────────
WHERE THIS FITS IN THE PIPELINE
─────────────────────────────────────────────────────────────────

  document_ingest.py  → extracts raw text from PDF/DOCX/Image
                         ↓
  THIS FILE           → operates on that extracted text to produce:
                         1. summarize_document()   — structured contract summary
                         2. extract_clauses()      — individual clause identification
                         3. detect_risks()         — RAG-grounded risk/compliance flags
                         4. full_document_analysis()— runs all three in sequence

  Next →  FastAPI /analyze endpoint wires full_document_analysis()
          result stored in PostgreSQL  risk_flags + chat_history tables

─────────────────────────────────────────────────────────────────
REUSED FROM rag_pipeline.py (no duplication)
─────────────────────────────────────────────────────────────────
  get_clients()                  — cached ChromaDB + embed model + Gemini client
  retrieve_chunks_for_query()    — embed query → ChromaDB top-K retrieval
  call_gemini()                  — Gemini API call with rate-limit retry + fallback
  LEGAL_DISCLAIMER               — mandatory disclaimer text
  GEMINI_MODEL                   — model name constant

─────────────────────────────────────────────────────────────────
HOW TO RUN
─────────────────────────────────────────────────────────────────

  All analysis modes on one file:
      python document_processor.py --file data/sample_contracts/Sample_2_Risky_Employment_Contract.pdf --mode all

  Individual modes:
      python document_processor.py --file <path> --mode summarize
      python document_processor.py --file <path> --mode clauses
      python document_processor.py --file <path> --mode risks
      python document_processor.py --file <path> --mode risks --doc-type "Employment Contract"

  Save JSON output to a file:
      python document_processor.py --file <path> --mode all --save-json

─────────────────────────────────────────────────────────────────
DEPENDENCIES
─────────────────────────────────────────────────────────────────
  All already in requirements.txt:
      google-genai  python-dotenv  chromadb  sentence-transformers
      langchain-text-splitters  pymupdf  python-docx  pytesseract  Pillow
─────────────────────────────────────────────────────────────────
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

# ── Import shared infrastructure from rag_pipeline ────────────────────────────
# get_clients()               → (collection, embed_model, gemini_client) singletons
# retrieve_chunks_for_query() → embed a string and pull top-K chunks from ChromaDB
# call_gemini()               → Gemini API call with retry logic
# LEGAL_DISCLAIMER            → mandatory disclaimer string
# GEMINI_MODEL                → model name for display in results
from rag_pipeline import (
    call_gemini,
    get_clients,
    LEGAL_DISCLAIMER,
    GEMINI_MODEL,
    retrieve_chunks_for_query,
)

# ── Import document_ingest for the CLI file-reading path ──────────────────────
from document_ingest import extract_text

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Documents under this character count are processed in a single Gemini call.
# Longer documents use map-reduce (section summarise → combine).
SINGLE_PASS_CHAR_LIMIT: int = 15_000

# Section size when splitting long documents for map-reduce summarisation.
# Kept larger than the RAG chunk size (700 chars) because we want coherent
# sections, not fine-grained retrieval chunks.
SUMMARY_SECTION_SIZE: int = 3_500
SUMMARY_SECTION_OVERLAP: int = 200

# Number of ChromaDB reference chunks to retrieve for grounding risk analysis
RISK_RAG_TOP_K: int = 6

# Minimum Gemini response length to consider a parse attempt worthwhile
MIN_RESPONSE_LENGTH: int = 20


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_gemini_client():
    """
    Return the cached Gemini client from rag_pipeline's shared singleton pool.
    Calling get_clients() the first time loads ChromaDB + embedding model too,
    so subsequent calls are essentially free (already cached).
    """
    _, _, gemini_client = get_clients()
    return gemini_client


def _call_gemini_safe(prompt: str, context_label: str = "Gemini call") -> str:
    """
    Wrapper around rag_pipeline.call_gemini() that catches all exceptions and
    returns an error string rather than propagating — keeps batch processing
    alive even when one Gemini call fails (e.g. transient 503).
    """
    try:
        client = _get_gemini_client()
        return call_gemini(prompt, client)
    except Exception as exc:
        return f"[ERROR in {context_label}: {type(exc).__name__}: {exc}]"


def _split_into_sections(text: str) -> list[str]:
    """
    Split a long document text into overlapping sections using LangChain's
    RecursiveCharacterTextSplitter — the same splitter used in chunking.py,
    but with much larger section sizes suited for summarisation rather than
    fine-grained retrieval.

    Splitting priority: double-newline (paragraph) → single newline → sentence
    end → word boundary.  This avoids cutting mid-sentence.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=SUMMARY_SECTION_SIZE,
        chunk_overlap=SUMMARY_SECTION_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


def _parse_json_from_gemini(raw: str, context_label: str) -> tuple[any, bool, str]:
    """
    Robustly parse a JSON response from Gemini.

    Gemini frequently wraps its JSON in markdown code fences:
        ```json
        [ ... ]
        ```
    We strip those before parsing.  If parsing still fails we return
    (None, False, error_message) so callers can handle gracefully.

    Returns:
        (parsed_object, success: bool, error_message: str)
    """
    if not raw or len(raw.strip()) < MIN_RESPONSE_LENGTH:
        return None, False, f"Empty or too-short response from Gemini ({context_label})"

    # ── Strip markdown code fences (```json ... ``` or ``` ... ```) ───────────
    cleaned = raw.strip()

    # Remove opening fence: ```json or ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    # Remove closing fence
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    # Sometimes Gemini adds prose before/after the JSON block.
    # Try to extract the first [...] or {...} block if direct parse fails.
    try:
        return json.loads(cleaned), True, ""
    except json.JSONDecodeError:
        pass

    # Attempt to find a JSON array first, then object
    for pattern in (r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"):
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group(1)), True, ""
            except json.JSONDecodeError:
                continue

    return (
        None,
        False,
        f"JSON parse failed for {context_label}. Raw response (first 300 chars): {raw[:300]}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. CONTRACT SUMMARISATION
# ─────────────────────────────────────────────────────────────────────────────

def _build_summarise_prompt(text_section: str, is_final_combine: bool = False) -> str:
    """
    Build the Gemini prompt for either:
      - A single section of the document (is_final_combine=False)
      - The final "combine section summaries" step (is_final_combine=True)

    Both prompts demand the same structured output so the caller can treat
    them uniformly.
    """
    role = (
        "You are an expert legal document analyst helping small business owners "
        "in India understand their contracts quickly and clearly."
    )

    if is_final_combine:
        instruction = (
            "Below are individual section summaries of a legal contract. "
            "Your task is to combine them into ONE coherent final summary.\n\n"
            "Your final summary MUST cover ALL of the following points "
            "(use these exact headings):\n"
            "  1. Parties Involved — who are the parties to this agreement?\n"
            "  2. Type of Agreement — what kind of contract is this?\n"
            "  3. Key Obligations — what must each party do?\n"
            "  4. Payment / Compensation Terms — any salary, fees, or payment details.\n"
            "  5. Duration / Term — how long does the agreement last?\n"
            "  6. Termination Conditions — how and when can it be ended?\n\n"
            "After the structured summary, list 5–8 KEY POINTS as a JSON array of strings.\n\n"
            "RESPOND ONLY with a JSON object in this exact schema:\n"
            "{\n"
            '  "summary": "<full structured summary with the 6 headings above>",\n'
            '  "key_points": ["<point 1>", "<point 2>", "..."]\n'
            "}\n\n"
            "Do NOT include any text before or after the JSON. No markdown fences.\n\n"
            "SECTION SUMMARIES TO COMBINE:\n"
        )
    else:
        instruction = (
            "Summarise the following section of a legal contract.\n"
            "Focus on: parties, obligations, payment terms, duration, termination.\n"
            "Be concise but don't omit important legal details.\n\n"
            "RESPOND ONLY with a JSON object:\n"
            "{\n"
            '  "summary": "<concise section summary>",\n'
            '  "key_points": ["<point 1>", "<point 2>"]\n'
            "}\n\n"
            "No markdown fences. No text outside the JSON.\n\n"
            "CONTRACT SECTION:\n"
        )

    return f"{role}\n\n{instruction}\n{text_section}\n"


def summarize_document(document_text: str, filename: str) -> dict:
    """
    Summarise a legal document using Gemini.

    Strategy
    ────────
    Short documents (< SINGLE_PASS_CHAR_LIMIT chars):
        Single Gemini call — fastest, highest quality.

    Long documents (≥ SINGLE_PASS_CHAR_LIMIT chars):
        Map-Reduce:
          1. Split into ~3500-char overlapping sections.
          2. Summarise each section individually (map step).
          3. Feed all section summaries into one final combining call (reduce step).
        This stays within Gemini's context window even for very long contracts.

    Args:
        document_text: Full extracted text of the document.
        filename:      Original filename (for display only).

    Returns:
        {
            "filename":           str,
            "summary":            str,   # structured 6-point summary
            "key_points":         list[str],
            "method":             "single-pass" | "map-reduce",
            "sections_processed": int,
            "model":              str,
        }
    """
    print(f"  📝 Summarising '{filename}' ({len(document_text):,} chars)...")

    # ── Choose strategy based on document length ──────────────────────────────
    if len(document_text) < SINGLE_PASS_CHAR_LIMIT:
        # ─ Single-pass ────────────────────────────────────────────────────────
        prompt = _build_summarise_prompt(document_text, is_final_combine=False)
        raw = _call_gemini_safe(prompt, "single-pass summarise")
        parsed, ok, err = _parse_json_from_gemini(raw, "summarise")

        if ok and isinstance(parsed, dict):
            return {
                "filename":           filename,
                "summary":            parsed.get("summary", raw),
                "key_points":         parsed.get("key_points", []),
                "method":             "single-pass",
                "sections_processed": 1,
                "model":              GEMINI_MODEL,
            }
        # Fallback: return raw text if JSON parsing failed
        return {
            "filename":           filename,
            "summary":            raw,
            "key_points":         [],
            "method":             "single-pass",
            "sections_processed": 1,
            "model":              GEMINI_MODEL,
            "_parse_warning":     err,
        }

    else:
        # ─ Map-Reduce ─────────────────────────────────────────────────────────
        sections = _split_into_sections(document_text)
        print(f"     Map-reduce: {len(sections)} sections → Gemini ...")

        section_summaries: list[str] = []
        for i, section in enumerate(sections, start=1):
            print(f"     Summarising section {i}/{len(sections)}...", end=" ", flush=True)
            prompt = _build_summarise_prompt(section, is_final_combine=False)
            raw = _call_gemini_safe(prompt, f"map section {i}")
            parsed, ok, _ = _parse_json_from_gemini(raw, f"map section {i}")

            if ok and isinstance(parsed, dict):
                section_summaries.append(parsed.get("summary", raw))
            else:
                section_summaries.append(raw)  # use raw if parse fails
            print("✓")

        # Combine all section summaries in one final call
        combined_input = "\n\n---\n\n".join(
            f"[Section {i}]\n{s}" for i, s in enumerate(section_summaries, 1)
        )
        print(f"     Combining {len(section_summaries)} section summaries...", end=" ", flush=True)
        final_prompt = _build_summarise_prompt(combined_input, is_final_combine=True)
        final_raw = _call_gemini_safe(final_prompt, "map-reduce combine")
        final_parsed, ok, err = _parse_json_from_gemini(final_raw, "map-reduce combine")
        print("✓")

        if ok and isinstance(final_parsed, dict):
            return {
                "filename":           filename,
                "summary":            final_parsed.get("summary", final_raw),
                "key_points":         final_parsed.get("key_points", []),
                "method":             "map-reduce",
                "sections_processed": len(sections),
                "model":              GEMINI_MODEL,
            }
        return {
            "filename":           filename,
            "summary":            final_raw,
            "key_points":         [],
            "method":             "map-reduce",
            "sections_processed": len(sections),
            "model":              GEMINI_MODEL,
            "_parse_warning":     err,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2. CLAUSE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

_CLAUSE_SCHEMA_EXAMPLE = (
    '[\n'
    '  {"clause_type": "Termination", "clause_text": "...", "clause_number_or_location": "Clause 7"},\n'
    '  {"clause_type": "Confidentiality", "clause_text": "...", "clause_number_or_location": "Clause 3"}\n'
    ']'
)

def _build_clause_extraction_prompt(document_text: str) -> str:
    """
    Build the Gemini prompt for clause extraction.

    We explicitly list the clause types the model should look for, provide
    the exact JSON schema, and forbid any non-JSON output — this minimises
    parsing failures.
    """
    return (
        "You are an expert legal document analyst. Your task is to identify and "
        "extract every distinct legal clause from the contract below.\n\n"
        "For each clause, identify its TYPE from this list (use these exact names "
        "where they match; use a descriptive name if none match):\n"
        "  Parties, Recitals, Definitions, Scope of Work, Term / Duration, "
        "Payment Terms, Salary / Compensation, Confidentiality / NDA, "
        "Non-Compete, Non-Solicitation, Intellectual Property / Ownership, "
        "Termination, Notice Period, Indemnification, Limitation of Liability, "
        "Dispute Resolution / Arbitration, Governing Law / Jurisdiction, "
        "Force Majeure, Assignment, Amendments / Modifications, Entire Agreement, "
        "Representations & Warranties, Penalty / Liquidated Damages, "
        "Working Hours, Leave Policy, Employee Obligations, Employer Obligations, "
        "Other.\n\n"
        "STRICT OUTPUT RULES:\n"
        "1. Return ONLY a valid JSON array — no text before or after, no markdown fences.\n"
        "2. Each element must have exactly these three keys:\n"
        '   "clause_type"              (string — the type name from the list above)\n'
        '   "clause_text"              (string — the actual text of the clause, verbatim or closely paraphrased)\n'
        '   "clause_number_or_location"(string — clause number, section heading, or "Not specified")\n'
        "3. If a clause type appears multiple times, include each occurrence separately.\n"
        "4. Do NOT merge clauses. Keep them separate.\n\n"
        f"EXAMPLE OUTPUT FORMAT:\n{_CLAUSE_SCHEMA_EXAMPLE}\n\n"
        "CONTRACT TEXT:\n"
        f"{document_text}\n\n"
        "EXTRACTED CLAUSES (JSON array only):"
    )


def extract_clauses(document_text: str, filename: str) -> dict:
    """
    Identify and extract individual legal clauses from a document using Gemini.

    Gemini is prompted to return strict JSON.  A robust parser strips markdown
    fences and attempts multiple extraction strategies before giving up.

    Args:
        document_text: Full extracted text of the document.
        filename:      Original filename (for display).

    Returns:
        {
            "filename":           str,
            "clauses":            list[dict],  # [{clause_type, clause_text, clause_number_or_location}]
            "total_clauses_found":int,
            "parse_success":      bool,
            "model":              str,
            "_parse_error":       str   # only present if parse_success is False
        }
    """
    print(f"  🔍 Extracting clauses from '{filename}'...")

    # For very long documents, use only the first SINGLE_PASS_CHAR_LIMIT chars
    # (clause extraction is most useful on the main body; tails are often boilerplate)
    text_for_extraction = document_text
    truncated = False
    if len(document_text) > SINGLE_PASS_CHAR_LIMIT:
        text_for_extraction = document_text[:SINGLE_PASS_CHAR_LIMIT]
        truncated = True
        print(f"     (document truncated to {SINGLE_PASS_CHAR_LIMIT:,} chars for clause extraction)")

    prompt = _build_clause_extraction_prompt(text_for_extraction)
    raw = _call_gemini_safe(prompt, "clause extraction")
    clauses, ok, err = _parse_json_from_gemini(raw, "clause extraction")

    result: dict = {
        "filename":            filename,
        "clauses":             [],
        "total_clauses_found": 0,
        "parse_success":       False,
        "model":               GEMINI_MODEL,
    }

    if truncated:
        result["_truncation_note"] = (
            f"Document was longer than {SINGLE_PASS_CHAR_LIMIT} chars; "
            "clause extraction ran on the first portion only."
        )

    if ok and isinstance(clauses, list):
        # Validate each clause has the required keys; filter bad entries silently
        valid_clauses = [
            c for c in clauses
            if isinstance(c, dict)
            and "clause_type" in c
            and "clause_text" in c
        ]
        result["clauses"]             = valid_clauses
        result["total_clauses_found"] = len(valid_clauses)
        result["parse_success"]       = True
        print(f"     Found {len(valid_clauses)} clause(s).")
    else:
        result["_parse_error"] = err or "Unknown parse failure"
        # Store raw response so user can inspect it
        result["_raw_response"] = raw[:800] if raw else ""
        print(f"     ⚠️  Clause JSON parse failed: {err}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. RISK / COMPLIANCE DETECTION  (RAG-grounded)
# ─────────────────────────────────────────────────────────────────────────────

_RISK_SCHEMA_EXAMPLE = (
    '[\n'
    '  {\n'
    '    "clause_type": "Non-Compete",\n'
    '    "risk_level": "High",\n'
    '    "issue_description": "Non-compete duration of 5 years is unusually long ...",\n'
    '    "recommendation": "Ask to reduce to 6–12 months and limit to the same industry."\n'
    '  }\n'
    ']'
)

_RISK_LEVELS_ORDER = {"High": 3, "Medium": 2, "Low": 1}


def _compute_overall_risk(flagged_issues: list[dict]) -> str:
    """
    Aggregate individual risk levels into one document-level score.
    Rule: any High → document is High; else any Medium → Medium; else Low.
    """
    if not flagged_issues:
        return "Low"
    highest = max(
        _RISK_LEVELS_ORDER.get(issue.get("risk_level", "Low"), 1)
        for issue in flagged_issues
    )
    return {3: "High", 2: "Medium", 1: "Low"}.get(highest, "Low")


def _build_risk_prompt(
    document_text: str,
    filename: str,
    document_type: str,
    reference_context: str,
    extracted_clauses: list[dict] | None,
) -> str:
    """
    Build the RAG-grounded risk detection prompt.

    The prompt feeds Gemini:
      1. The uploaded document's text (or extracted clause list if available).
      2. Reference context pulled from ChromaDB (fair/standard clause language
         from templates and compliance docs) — this is what makes it RAG-grounded
         rather than a raw LLM opinion.
      3. Strict JSON output schema with four required fields per issue.
    """
    # If we have extracted clauses, format them more cleanly than raw text
    if extracted_clauses:
        doc_section = "UPLOADED DOCUMENT — EXTRACTED CLAUSES:\n" + "\n".join(
            f"[{c.get('clause_number_or_location', '?')}] "
            f"{c.get('clause_type', 'Unknown')}: {c.get('clause_text', '')[:600]}"
            for c in extracted_clauses
        )
    else:
        doc_section = (
            "UPLOADED DOCUMENT TEXT:\n"
            + document_text[:SINGLE_PASS_CHAR_LIMIT]
        )

    doc_type_note = f"Document type: {document_type}" if document_type else ""

    return (
        "You are an expert legal risk analyst helping small business owners in India "
        "identify unfair, risky, or non-compliant clauses in their contracts.\n\n"
        + (f"{doc_type_note}\n\n" if doc_type_note else "")
        + "─" * 60 + "\n"
        "REFERENCE MATERIAL (standard/fair clause language from a legal knowledge base):\n"
        "─" * 60 + "\n"
        + reference_context + "\n"
        "─" * 60 + "\n\n"
        + doc_section + "\n\n"
        "─" * 60 + "\n"
        "YOUR TASK:\n"
        "Analyse the uploaded document against the reference material and Indian business "
        "practice. Flag clauses that are:\n"
        "  • One-sided or unfair to one party\n"
        "  • Missing entirely when they are standard for this type of agreement\n"
        "  • Unusually vague or undefined\n"
        "  • Non-compliant with general Indian law (e.g., no notice period, "
        "unlimited liability, unreasonable non-compete, arbitrary deductions, "
        "excessive working hours without overtime)\n\n"
        "For each flagged issue, assess risk level:\n"
        "  High   — could cause significant legal/financial harm if signed as-is\n"
        "  Medium — concerning but negotiable; should be reviewed by a lawyer\n"
        "  Low    — minor issue; good to know but unlikely to cause serious harm\n\n"
        "STRICT OUTPUT RULES:\n"
        "1. Return ONLY a valid JSON array — no prose, no markdown fences.\n"
        "2. Each element must have exactly these four keys:\n"
        '   "clause_type"       (string — the clause this issue relates to)\n'
        '   "risk_level"        (string — must be exactly "High", "Medium", or "Low")\n'
        '   "issue_description" (string — plain-language explanation of the problem)\n'
        '   "recommendation"    (string — practical suggestion for the business owner)\n'
        "3. If you find NO issues, return an empty array: []\n\n"
        f"EXAMPLE FORMAT:\n{_RISK_SCHEMA_EXAMPLE}\n\n"
        "FLAGGED ISSUES (JSON array only):"
    )


def detect_risks(
    document_text: str,
    filename: str,
    document_type: str | None = None,
    _precomputed_clauses: list[dict] | None = None,
) -> dict:
    """
    Detect risky, unfair, or non-compliant clauses — RAG-grounded.

    RAG grounding steps
    ───────────────────
    1. Build two retrieval queries from the document type + key risk topics.
    2. Retrieve reference chunks from ChromaDB (templates category first,
       then compliance_docs) — these are fair/standard clause examples.
    3. Format retrieved context and pass it alongside the document into Gemini.
    4. Gemini compares the uploaded document against the standard reference.

    This is fundamentally different from a raw LLM call — the risk flags are
    grounded in the actual legal knowledge base, not just model knowledge.

    Args:
        document_text:        Full extracted text of the document.
        filename:             Original filename.
        document_type:        e.g. "Employment Contract", "NDA", "Rental Agreement".
                              Used to focus the RAG retrieval query.
                              If None, the system infers from text heuristics.
        _precomputed_clauses: If extract_clauses() has already run, pass its
                              result here to avoid re-running it; provides cleaner
                              structured input to the risk prompt.

    Returns:
        {
            "filename":          str,
            "overall_risk_score":"High" | "Medium" | "Low",
            "flagged_issues":    list[dict],
            "total_issues_found":int,
            "rag_sources_used":  list[str],   # filenames of retrieved reference docs
            "disclaimer":        str,
            "model":             str,
            "_parse_error":      str,          # only if JSON parse failed
        }
    """
    print(f"  ⚠️  Detecting risks in '{filename}'...")

    # ── Step 1: Build RAG retrieval queries ───────────────────────────────────
    # We query with multiple topic strings to maximise relevant reference coverage.
    doc_type_str = document_type or "business contract"
    rag_queries = [
        f"standard clauses for {doc_type_str}",
        "termination notice period employee rights",
        "non-compete clause duration India reasonable",
        "payment terms liability indemnification",
        "working hours overtime India labour law",
    ]

    # ── Step 2: Retrieve reference chunks from ChromaDB ───────────────────────
    # Try templates first (standard contract language), then compliance_docs
    all_ref_chunks: list[dict] = []
    seen_texts: set[str] = set()

    for query in rag_queries:
        for category in ("templates", "compliance_docs"):
            chunks = retrieve_chunks_for_query(
                query, top_k=2, category_filter=category
            )
            for chunk in chunks:
                # Deduplicate by first 100 chars of text
                key = chunk["text"][:100]
                if key not in seen_texts:
                    seen_texts.add(key)
                    all_ref_chunks.append(chunk)

        if len(all_ref_chunks) >= RISK_RAG_TOP_K:
            break

    # Format retrieved chunks into a readable context block
    if all_ref_chunks:
        reference_context = "\n\n".join(
            f"[Ref {i}: {c['filename']} | {c['category']} | "
            f"similarity: {c['similarity']}]\n{c['text']}"
            for i, c in enumerate(all_ref_chunks[:RISK_RAG_TOP_K], 1)
        )
        rag_sources = list({c["filename"] for c in all_ref_chunks[:RISK_RAG_TOP_K]})
        print(f"     RAG: {len(all_ref_chunks[:RISK_RAG_TOP_K])} reference chunks "
              f"from {len(rag_sources)} source(s).")
    else:
        # ChromaDB might not be populated yet — continue with no reference context
        reference_context = (
            "No reference material retrieved from knowledge base. "
            "Analyse based on general Indian business contract standards."
        )
        rag_sources = []
        print("     ⚠️  No RAG reference chunks found — proceeding without KB context.")

    # ── Step 3: Build and call the risk prompt ────────────────────────────────
    prompt = _build_risk_prompt(
        document_text=document_text,
        filename=filename,
        document_type=document_type or "",
        reference_context=reference_context,
        extracted_clauses=_precomputed_clauses,
    )

    raw = _call_gemini_safe(prompt, "risk detection")
    issues, ok, err = _parse_json_from_gemini(raw, "risk detection")

    # ── Step 4: Build result ──────────────────────────────────────────────────
    result: dict = {
        "filename":           filename,
        "overall_risk_score": "Low",
        "flagged_issues":     [],
        "total_issues_found": 0,
        "rag_sources_used":   rag_sources,
        "disclaimer":         LEGAL_DISCLAIMER,
        "model":              GEMINI_MODEL,
    }

    if ok and isinstance(issues, list):
        # Normalise risk_level capitalisation (Gemini sometimes returns "high")
        for issue in issues:
            if "risk_level" in issue:
                lvl = str(issue["risk_level"]).capitalize()
                issue["risk_level"] = lvl if lvl in ("High", "Medium", "Low") else "Medium"

        result["flagged_issues"]     = issues
        result["total_issues_found"] = len(issues)
        result["overall_risk_score"] = _compute_overall_risk(issues)
        print(f"     Found {len(issues)} issue(s). "
              f"Overall risk: {result['overall_risk_score']}")
    else:
        result["_parse_error"]  = err or "Unknown parse failure"
        result["_raw_response"] = raw[:800] if raw else ""
        print(f"     ⚠️  Risk JSON parse failed: {err}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. COMBINED ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def full_document_analysis(
    document_text: str,
    filename: str,
    document_type: str | None = None,
) -> dict:
    """
    Run all three processing functions in sequence and return a single combined dict.

    Execution order matters:
      1. extract_clauses()   — clause list is passed to detect_risks() for cleaner
                               structured input (avoids re-processing raw text).
      2. summarize_document()
      3. detect_risks()      — receives precomputed clauses from step 1.

    This is the function to wire into the FastAPI /analyze endpoint:

        from document_processor import full_document_analysis

        @app.post("/documents/{doc_id}/analyze")
        async def analyze(doc_id: str):
            text = get_text_from_db(doc_id)
            return full_document_analysis(text, filename, document_type)

    Returns:
        {
            "filename":      str,
            "summary_result":  dict,   # from summarize_document()
            "clause_result":   dict,   # from extract_clauses()
            "risk_result":     dict,   # from detect_risks()
        }
    """
    print(f"\n{'='*65}")
    print(f"  FULL DOCUMENT ANALYSIS: {filename}")
    print(f"{'='*65}")

    # Step 1: Extract clauses first (reused by risk detection)
    clause_result = extract_clauses(document_text, filename)

    # Step 2: Summarise
    summary_result = summarize_document(document_text, filename)

    # Step 3: Risk detection — pass pre-extracted clauses to avoid redundant work
    precomputed = clause_result.get("clauses") if clause_result.get("parse_success") else None
    risk_result = detect_risks(
        document_text,
        filename,
        document_type=document_type,
        _precomputed_clauses=precomputed,
    )

    print(f"\n✅ Analysis complete for '{filename}'")
    print(f"   Clauses found  : {clause_result.get('total_clauses_found', '?')}")
    print(f"   Issues flagged : {risk_result.get('total_issues_found', '?')}")
    print(f"   Overall risk   : {risk_result.get('overall_risk_score', '?')}")
    print(f"{'='*65}\n")

    return {
        "filename":      filename,
        "summary_result": summary_result,
        "clause_result":  clause_result,
        "risk_result":    risk_result,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRETTY-PRINT HELPERS  (CLI output)
# ─────────────────────────────────────────────────────────────────────────────

def _print_summary(result: dict) -> None:
    print("\n" + "═" * 65)
    print("  📋 SUMMARY")
    print("═" * 65)
    print(f"  File    : {result.get('filename')}")
    print(f"  Method  : {result.get('method')}  "
          f"({result.get('sections_processed', 1)} section(s))")
    print(f"  Model   : {result.get('model')}")
    print("\n" + result.get("summary", "(no summary)"))

    kp = result.get("key_points", [])
    if kp:
        print("\n  KEY POINTS:")
        for i, point in enumerate(kp, 1):
            print(f"    {i}. {point}")
    if "_parse_warning" in result:
        print(f"\n  ⚠️  Parse warning: {result['_parse_warning']}")
    print("─" * 65)


def _print_clauses(result: dict) -> None:
    print("\n" + "═" * 65)
    print(f"  🔍 EXTRACTED CLAUSES  ({result.get('total_clauses_found', 0)} found)")
    print("═" * 65)
    print(f"  File         : {result.get('filename')}")
    print(f"  Parse success: {result.get('parse_success')}")

    if "_truncation_note" in result:
        print(f"  ⚠️  {result['_truncation_note']}")

    clauses = result.get("clauses", [])
    if not clauses:
        if "_parse_error" in result:
            print(f"\n  ❌ Parse error: {result['_parse_error']}")
            if "_raw_response" in result:
                print(f"  Raw (first 300 chars): {result['_raw_response'][:300]}")
        else:
            print("\n  No clauses extracted.")
    else:
        for i, clause in enumerate(clauses, 1):
            loc  = clause.get("clause_number_or_location", "?")
            ctype = clause.get("clause_type", "Unknown")
            text  = clause.get("clause_text", "")
            preview = text[:250].replace("\n", " ")
            if len(text) > 250:
                preview += "..."
            print(f"\n  ┌─ [{i}] {ctype}  ({loc})")
            print(f"  │  {preview}")
            print(f"  └{'─' * 60}")
    print()


def _print_risks(result: dict) -> None:
    RISK_ICONS = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}

    print("\n" + "═" * 65)
    overall = result.get("overall_risk_score", "Unknown")
    icon = RISK_ICONS.get(overall, "⚪")
    print(f"  ⚠️  RISK ANALYSIS  —  Overall Score: {icon} {overall}")
    print("═" * 65)
    print(f"  File         : {result.get('filename')}")
    print(f"  Issues found : {result.get('total_issues_found', 0)}")
    sources = result.get("rag_sources_used", [])
    if sources:
        print(f"  RAG sources  : {', '.join(sources)}")
    print()

    issues = result.get("flagged_issues", [])
    if not issues:
        if "_parse_error" in result:
            print(f"  ❌ Parse error: {result['_parse_error']}")
        else:
            print("  ✅ No significant risks flagged.")
    else:
        for i, issue in enumerate(issues, 1):
            lvl   = issue.get("risk_level", "?")
            ctype = issue.get("clause_type", "Unknown")
            desc  = issue.get("issue_description", "")
            rec   = issue.get("recommendation", "")
            icon  = RISK_ICONS.get(lvl, "⚪")

            print(f"  ┌─ [{i}] {icon} {lvl} risk — {ctype}")
            print(f"  │  Issue : {desc}")
            print(f"  │  Action: {rec}")
            print(f"  └{'─' * 60}")

    print(f"\n  ⚖️  {result.get('disclaimer', LEGAL_DISCLAIMER)}")
    print("─" * 65)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Document processing: summarize / extract clauses / detect risks\n"
            "  python document_processor.py --file <path> --mode all"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to a PDF, DOCX, or image file to analyse.",
    )
    parser.add_argument(
        "--mode",
        choices=["summarize", "clauses", "risks", "all"],
        default="all",
        help=(
            "Which analysis to run:\n"
            "  summarize — contract summary\n"
            "  clauses   — clause extraction\n"
            "  risks     — risk/compliance detection (RAG-grounded)\n"
            "  all       — run all three (default)"
        ),
    )
    parser.add_argument(
        "--doc-type",
        type=str,
        default=None,
        metavar="TYPE",
        help=(
            "Optional document type hint for risk analysis, e.g. "
            '"Employment Contract", "NDA", "Rental Agreement".'
        ),
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the full result dict to a JSON file alongside the input file.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"\n❌ File not found: {file_path}")
        sys.exit(1)

    print("=" * 65)
    print("  DOCUMENT PROCESSOR — AI Legal Document Assistant")
    print("=" * 65)
    print(f"\n📄 File : {file_path.name}")
    print(f"   Mode : {args.mode}")
    if args.doc_type:
        print(f"   Type : {args.doc_type}")

    # ── Extract text from file ────────────────────────────────────────────────
    print("\n⏳ Extracting text...")
    ingest_result = extract_text(file_path)

    if not ingest_result["text"].strip():
        print(f"\n❌ No text could be extracted from '{file_path.name}'.")
        if ingest_result["warnings"]:
            for w in ingest_result["warnings"]:
                print(f"   Warning: {w}")
        sys.exit(1)

    document_text = ingest_result["text"]
    filename      = ingest_result["filename"]
    extraction_method = ingest_result.get("extraction_method", "unknown")
    print(f"   Extracted {len(document_text):,} chars via {extraction_method}.")
    if ingest_result.get("warnings"):
        for w in ingest_result["warnings"]:
            print(f"   ⚠️  {w}")

    # ── Run requested mode(s) ─────────────────────────────────────────────────
    full_result: dict = {}

    if args.mode == "all":
        full_result = full_document_analysis(document_text, filename, args.doc_type)
        _print_summary(full_result["summary_result"])
        _print_clauses(full_result["clause_result"])
        _print_risks(full_result["risk_result"])

    elif args.mode == "summarize":
        res = summarize_document(document_text, filename)
        _print_summary(res)
        full_result = res

    elif args.mode == "clauses":
        res = extract_clauses(document_text, filename)
        _print_clauses(res)
        full_result = res

    elif args.mode == "risks":
        res = detect_risks(document_text, filename, document_type=args.doc_type)
        _print_risks(res)
        full_result = res

    # ── Optionally save JSON ──────────────────────────────────────────────────
    if args.save_json:
        out_path = file_path.with_stem(file_path.stem + f"_{args.mode}_result").with_suffix(".json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(full_result, fh, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved → {out_path}")


if __name__ == "__main__":
    main()
