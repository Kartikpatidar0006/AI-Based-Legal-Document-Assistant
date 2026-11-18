"""
Reproducible Evaluation Pipeline
AI-Based Legal Document Assistant -- Major Project

Evaluates three systems on the same 15-question benchmark:
  1. B1: Ungrounded Gemini (zero retrieval / no document grounding)
  2. B2: BM25 retrieval + Gemini (sparse keyword retrieval)
  3. P:  Proposed dense RAG (all-MiniLM-L6-v2 + ChromaDB + Gemini)

Conditions:
  - Seed: 42
  - Temperature: 0.0
  - Top-K retrieval: 7
  - Primary Model: gemini-3.1-flash-lite
  - Fallbacks: gemini-3-flash-preview, gemini-flash-lite-latest
  - Testing notes completely stripped before model prompting
  - Incremental checkpointing per query
"""

import csv
import json
import math
import os
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths and Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "evaluation"
EVAL_DIR.mkdir(exist_ok=True)

QUESTIONS_CSV     = EVAL_DIR / "evaluation_questions.csv"
GROUND_TRUTH_CSV  = EVAL_DIR / "risk_ground_truth.csv"
CHECKPOINT_JSON   = EVAL_DIR / "evaluation_checkpoint.json"
PREDICTIONS_JSONL = EVAL_DIR / "raw_predictions.jsonl"
TABLE7_CSV        = EVAL_DIR / "table_7_results.csv"
TABLE8_CSV        = EVAL_DIR / "table_8_results.csv"
REPORT_MD         = EVAL_DIR / "evaluation_report.md"

CONTRACTS_DIR     = ROOT / "data" / "extracted_text"
CHUNKS_JSON       = ROOT / "data" / "chunks" / "all_chunks.json"
VECTOR_DB_PATH    = ROOT / "data" / "vector_db"
COLLECTION_NAME   = "legal_docs"
EMBEDDING_MODEL   = "all-MiniLM-L6-v2"

RANDOM_SEED        = 42
GEMINI_TEMPERATURE = 0.0
TOP_K_RETRIEVAL    = 7
BM25_TOP_K         = 7

CONTRACT_ID_MAP = {
    "Sample_1": "Sample_1_Balanced_Service_Agreement.txt",
    "Sample_2": "Sample_2_Risky_Employment_Contract.txt",
    "Sample_3": "Sample_3_Rental_Missing_Clauses.txt",
    "Sample_4": "Sample_4_Complex_NDA_Long.txt",
}

RISK_KEYWORDS = {
    "one-sided termination": [
        "without notice", "without any notice", "without cause", "no notice period",
        "no severance", "unilateral termination", "terminate at any time",
        "60 days", "one-sided termination", "employer can terminate",
        "forfeited", "forfeit", "asymmetric termination"
    ],
    "excessive working hours": [
        "no fixed upper limit", "unlimited hours", "no overtime",
        "no additional compensation", "excessive working", "no fixed hours",
        "unlimited working", "any hours required", "without overtime pay"
    ],
    "broad non-compete": [
        "non-compete", "non compete", "3 years", "three years",
        "anywhere in india", "entire india", "overly broad",
        "unreasonable non-compete", "all of india", "restraint of trade"
    ],
    "unilateral deductions": [
        "deduct", "without proof", "without investigation", "salary deduction",
        "arbitrary deduction", "without due process", "without requiring proof",
        "unilateral deduction", "perceived damages"
    ],
    "missing standard clause": [
        "missing", "no termination clause", "no dispute resolution",
        "no security deposit", "absent", "not present", "does not contain",
        "no clause", "omitted", "lacking", "not included", "does not specify"
    ],
}

FAITHFULNESS_POSITIVE = [
    "according to", "based on", "as stated in", "as per", "the document states",
    "clause", "section", "the agreement", "the contract", "under clause", "pursuant to"
]

FAITHFULNESS_NEGATIVE = [
    "generally", "typically", "usually", "in most cases", "as a rule of thumb",
    "i believe", "i think", "it is common", "standard practice", "most contracts"
]

CITATION_PATTERNS = [
    r"clause\s*\d+", r"section\s*\d+", r"\[source\s*\d+\]",
    r"sample_[1-4]", r"\.txt", r"\.pdf"
]

ABSTENTION_PHRASES = [
    "i don't have enough information",
    "i do not have enough information",
    "cannot answer",
    "not enough information",
    "document does not contain",
    "the document does not",
    "does not include",
    "not mentioned",
    "no provision",
    "not specified in the provided",
    "not present in the provided"
]

# ---------------------------------------------------------------------------
# Checkpoint Helpers
# ---------------------------------------------------------------------------

def load_checkpoint():
    if CHECKPOINT_JSON.exists():
        try:
            with open(CHECKPOINT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            return {}
    return {}

def save_to_checkpoint(entry):
    cache = load_checkpoint()
    key = f"{entry['system']}_{entry['qid']}"
    cache[key] = entry
    with open(CHECKPOINT_JSON, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def _print_section(title):
    bar = "=" * 70
    print(f"\n{bar}\n  {title}\n{bar}")

def strip_testing_notes(text):
    """
    Completely removes all TESTING NOTE sections and metadata prompts
    before sending text to any model.
    """
    if not text:
        return ""
    text = re.sub(
        r"TESTING NOTE.*?(?=(?:This\s+[A-Z]|WHEREAS|1\.\s+[A-Z]|\n\n\n))",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE
    )
    cleaned_lines = []
    for line in text.splitlines():
        lower = line.strip().lower()
        if any(tag in lower for tag in ["testing note", "expected system output", "testing risk-detection", "meant to test"]):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

def load_contract_text(contract_id):
    filename = CONTRACT_ID_MAP.get(contract_id)
    if not filename:
        return ""
    path = CONTRACTS_DIR / filename
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return ""
    return strip_testing_notes(path.read_text(encoding="utf-8", errors="replace"))

def load_questions():
    rows = []
    with open(QUESTIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"  OK: Loaded {len(rows)} evaluation questions")
    return rows

def load_ground_truth():
    rows = []
    with open(GROUND_TRUTH_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"  OK: Loaded {len(rows)} ground-truth risk entries")
    return rows

# ---------------------------------------------------------------------------
# Gemini Client & LLM Invocation
# ---------------------------------------------------------------------------

def init_gemini():
    load_dotenv(ROOT / ".env", override=True)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not found in .env")
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ.pop("GOOGLE_API_KEY", None)
    import google.genai as genai
    client = genai.Client(api_key=api_key)
    print("  OK: Gemini client initialised")
    return client

def call_gemini(prompt, client, max_retries=4):
    import google.genai.types as types
    candidates = ["gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-flash-lite-latest"]
    for attempt in range(1, max_retries + 1):
        for model_name in candidates:
            try:
                t0 = time.perf_counter()
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=GEMINI_TEMPERATURE,
                        seed=RANDOM_SEED
                    ),
                )
                latency = round(time.perf_counter() - t0, 3)
                text = response.text if response.text else ""
                if text:
                    return text, latency
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ["404", "not_found", "not found"]):
                    continue
                if any(x in err for x in ["503", "500", "overloaded", "unavailable"]):
                    wait = 6 * attempt
                    print(f"      [Retry {attempt}] 503 unavailable, waiting {wait}s ...")
                    time.sleep(wait)
                    continue
                if any(x in err for x in ["429", "quota", "rate"]):
                    wait = 30 * attempt
                    print(f"      [Retry {attempt}] 429 rate limit on {model_name}, waiting {wait}s ...")
                    time.sleep(wait)
                    continue
                print(f"      [Retry {attempt}] {type(e).__name__} on {model_name}: {e}")
                time.sleep(3)
                continue
    return "ERROR: Max retries exceeded", 0.0

# ---------------------------------------------------------------------------
# B1: Ungrounded Gemini (No Retrieval / No Document Grounding)
# ---------------------------------------------------------------------------

def run_b1(questions, client, cache):
    _print_section("B1 -- Ungrounded Gemini (no retrieval, no document context)")
    results = []
    for i, q in enumerate(questions, 1):
        key = f"B1_Ungrounded_{q['qid']}"
        if key in cache and not cache[key].get("response", "").startswith("ERROR:"):
            print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} ... [CACHED] {cache[key]['latency_s']:.2f}s")
            results.append(cache[key])
            continue

        prompt = (
            "You are an AI Legal Document Assistant. Answer the following question about "
            f"a legal contract ({q['contract_id']}) based solely on your internal knowledge "
            "without access to the document text.\n\n"
            f"QUESTION: {q['question']}\n\n"
            "ANSWER:"
        )
        print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} ...", end=" ", flush=True)
        resp, lat = call_gemini(prompt, client)
        print(f"{lat:.2f}s")
        entry = {
            "system": "B1_Ungrounded",
            "qid": q["qid"],
            "contract_id": q["contract_id"],
            "question": q["question"],
            "prompt_chars": len(prompt),
            "response": resp,
            "latency_s": lat,
            "retrieved_chunks": [],
            "top1_similarity": None,
        }
        save_to_checkpoint(entry)
        results.append(entry)
        time.sleep(3.0)
    return results

# ---------------------------------------------------------------------------
# B2: BM25 Retrieval + Gemini (Sparse Keyword Retrieval)
# ---------------------------------------------------------------------------

def _tokenise(text):
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())

def bm25_retrieve(query, corpus, top_k=BM25_TOP_K):
    k1, b = 1.5, 0.75
    qtoks = _tokenise(query)
    ctoks = [_tokenise(c["text"]) for c in corpus]
    N = len(corpus)
    avg_dl = sum(len(t) for t in ctoks) / max(N, 1)

    def idf(term):
        df = sum(1 for t in ctoks if term in t)
        return math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    scores = []
    for idx, tokens in enumerate(ctoks):
        tf_map = {}
        for t in tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        dl = len(tokens)
        score = 0.0
        for term in qtoks:
            tf = tf_map.get(term, 0)
            score += idf(term) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        scores.append((score, idx))

    scores.sort(key=lambda x: -x[0])
    ret = []
    for rank, (score, idx) in enumerate(scores[:top_k], 1):
        chunk = corpus[idx].copy()
        chunk["bm25_score"] = round(score, 4)
        chunk["rank"] = rank
        ret.append(chunk)
    return ret

def build_b2_corpus(contract_id):
    if not CHUNKS_JSON.exists():
        return []
    with open(CHUNKS_JSON, encoding="utf-8") as f:
        all_chunks = json.load(f)
    stem_map = {
        "Sample_1": "sample_1",
        "Sample_2": "sample_2",
        "Sample_3": "sample_3",
        "Sample_4": "sample_4",
    }
    stem = stem_map.get(contract_id, "")
    filtered = [
        c for c in all_chunks
        if stem and stem in c.get("filename", "").lower()
    ]
    target_corpus = filtered if filtered else all_chunks
    cleaned_corpus = []
    for c in target_corpus:
        cc = c.copy()
        cc["text"] = strip_testing_notes(cc.get("text", ""))
        cleaned_corpus.append(cc)
    return cleaned_corpus

def run_b2(questions, client, cache):
    _print_section("B2 -- BM25 Retrieval + Gemini (Sparse Keyword RAG)")
    results = []
    for i, q in enumerate(questions, 1):
        key = f"B2_BM25_{q['qid']}"
        if key in cache and not cache[key].get("response", "").startswith("ERROR:"):
            print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} ... [CACHED] {cache[key]['latency_s']:.2f}s")
            results.append(cache[key])
            continue

        corpus = build_b2_corpus(q["contract_id"])
        retrieved = bm25_retrieve(q["question"], corpus, top_k=BM25_TOP_K)
        ctx = "\n\n".join(
            f"[Source {j}: {c.get('filename','?')} | BM25:{c.get('bm25_score',0):.4f}]\n{strip_testing_notes(c['text'])}"
            for j, c in enumerate(retrieved, 1)
        )
        prompt = (
            "You are an AI Legal Document Assistant. Answer the question using ONLY the provided context.\n"
            "If the provided context does not contain enough information to answer, state clearly: "
            "\"I don't have enough information in the provided documents to answer this question.\"\n"
            "Cite source numbers and filenames where applicable.\n\n"
            f"CONTEXT:\n{ctx}\n\n"
            f"QUESTION: {q['question']}\n\n"
            "ANSWER:"
        )
        print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} (BM25 top-{len(retrieved)}) ...", end=" ", flush=True)
        resp, lat = call_gemini(prompt, client)
        print(f"{lat:.2f}s")
        entry = {
            "system": "B2_BM25",
            "qid": q["qid"],
            "contract_id": q["contract_id"],
            "question": q["question"],
            "prompt_chars": len(prompt),
            "response": resp,
            "latency_s": lat,
            "retrieved_chunks": [
                {
                    "rank": c.get("rank"),
                    "filename": c.get("filename"),
                    "bm25_score": c.get("bm25_score"),
                    "text": c.get("text", "")
                }
                for c in retrieved
            ],
            "top1_similarity": None,
        }
        save_to_checkpoint(entry)
        results.append(entry)
        time.sleep(3.0)
    return results

# ---------------------------------------------------------------------------
# P: Proposed Dense RAG (all-MiniLM-L6-v2 + ChromaDB + Gemini)
# ---------------------------------------------------------------------------

def init_chromadb():
    import chromadb
    if not VECTOR_DB_PATH.exists():
        raise FileNotFoundError(f"Vector DB not found at {VECTOR_DB_PATH}")
    cc = chromadb.PersistentClient(path=str(VECTOR_DB_PATH))
    col = cc.get_collection(name=COLLECTION_NAME)
    print(f"  OK: ChromaDB ready | {col.count()} vectors indexed")
    return col

def init_embed_model():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  OK: Embedding model: {EMBEDDING_MODEL}")
    return model

def dense_retrieve(question, collection, embed_model, top_k=TOP_K_RETRIEVAL):
    vector = embed_model.encode(question, convert_to_numpy=True).tolist()
    raw = collection.query(
        query_embeddings=[vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    docs  = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]
    return [
        {
            "rank": rank,
            "text": strip_testing_notes(doc),
            "filename": meta.get("filename", "?"),
            "category": meta.get("category", "?"),
            "chunk_index": meta.get("chunk_index", 0),
            "similarity": round(max(0.0, 1.0 - dist / 2.0), 4),
        }
        for rank, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1)
    ]

def run_proposed_rag(questions, client, collection, embed_model, cache):
    _print_section("P -- Proposed Dense RAG (Embeddings + ChromaDB + Gemini)")
    results = []
    for i, q in enumerate(questions, 1):
        key = f"P_DenseRAG_{q['qid']}"
        if key in cache and not cache[key].get("response", "").startswith("ERROR:"):
            print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} ... [CACHED] {cache[key]['latency_s']:.2f}s")
            results.append(cache[key])
            continue

        retrieved = dense_retrieve(q["question"], collection, embed_model, top_k=TOP_K_RETRIEVAL)
        top1_sim = retrieved[0]["similarity"] if retrieved else None
        ctx_lines = ["-" * 60, "CONTEXT SECTIONS (retrieved from vector database):", "-" * 60]
        for j, chunk in enumerate(retrieved, 1):
            ctx_lines.extend([
                f"\n[Source {j}: {chunk['filename']} | {chunk['category']} | sim:{chunk['similarity']}]",
                chunk["text"],
                ""
            ])
        ctx_lines.append("-" * 60)
        prompt = (
            "You are an AI Legal Document Assistant. Answer using ONLY the provided context.\n"
            "Rules:\n"
            "1. Answer solely based on the retrieved context below.\n"
            "2. If the context is insufficient, state: "
            "\"I don't have enough information in the provided documents to answer this question.\"\n"
            "3. Cite source numbers and filenames where applicable.\n"
            "4. Explain terms in plain English for a non-lawyer business owner.\n\n"
            f"{chr(10).join(ctx_lines)}\n\n"
            f"USER QUESTION: {q['question']}\n\n"
            "YOUR ANSWER:"
        )
        print(f"  [{i:02d}/{len(questions)}] {q['qid']} | {q['contract_id']} (sim={top1_sim}) ...", end=" ", flush=True)
        resp, lat = call_gemini(prompt, client)
        print(f"{lat:.2f}s")
        entry = {
            "system": "P_DenseRAG",
            "qid": q["qid"],
            "contract_id": q["contract_id"],
            "question": q["question"],
            "prompt_chars": len(prompt),
            "response": resp,
            "latency_s": lat,
            "retrieved_chunks": [
                {
                    "rank": c["rank"],
                    "filename": c["filename"],
                    "similarity": c["similarity"],
                    "text": c["text"]
                }
                for c in retrieved
            ],
            "top1_similarity": top1_sim,
        }
        save_to_checkpoint(entry)
        results.append(entry)
        time.sleep(3.0)
    return results

# ---------------------------------------------------------------------------
# Metric Calculations (Table 7)
# ---------------------------------------------------------------------------

def compute_precision_at_k(chunks, expected_clause, k=TOP_K_RETRIEVAL):
    """P@k = (# relevant in top-k) / k."""
    if not chunks or not expected_clause or "MISSING" in expected_clause.upper():
        return float("nan")
    keywords = [kw.lower().strip() for kw in re.split(r"[,\-]", expected_clause) if kw.strip()]
    hits = sum(
        1 for c in chunks[:k]
        if any(kw in (c.get("text", "") + " " + c.get("filename", "")).lower() for kw in keywords)
    )
    return round(hits / k, 4)

def compute_mrr(chunks, expected_clause):
    """MRR = 1/rank_first_relevant; 0 if none found."""
    if not chunks or not expected_clause or "MISSING" in expected_clause.upper():
        return float("nan")
    keywords = [kw.lower().strip() for kw in re.split(r"[,\-]", expected_clause) if kw.strip()]
    for rank, c in enumerate(chunks, 1):
        if any(kw in (c.get("text", "") + " " + c.get("filename", "")).lower() for kw in keywords):
            return round(1.0 / rank, 4)
    return 0.0

def compute_faithfulness(response):
    """pos / (pos + neg + 1). pos = grounded evidence phrases; neg = ungrounded generic phrases."""
    if not response or response.startswith("ERROR:"):
        return float("nan")
    lower = response.lower()
    pos = sum(1 for p in FAITHFULNESS_POSITIVE if p in lower)
    neg = sum(1 for p in FAITHFULNESS_NEGATIVE if p in lower)
    return round(pos / (pos + neg + 1), 4)

def compute_citation_accuracy(response):
    """Fraction of citation patterns found in response."""
    if not response or response.startswith("ERROR:"):
        return float("nan")
    lower = response.lower()
    hits = sum(1 for pat in CITATION_PATTERNS if re.search(pat, lower))
    return round(min(1.0, hits / 2.0), 4)

def compute_hallucination_rate(responses):
    """Fraction of responses that assert ungrounded generalizations without grounding."""
    valid = [r for r in responses if r and not r.startswith("ERROR:")]
    if not valid:
        return float("nan")
    hallucinated = 0
    for r in valid:
        lower = r.lower()
        pos = sum(1 for p in FAITHFULNESS_POSITIVE if p in lower)
        neg = sum(1 for p in FAITHFULNESS_NEGATIVE if p in lower)
        if neg > 0 and pos == 0:
            hallucinated += 1
    return round(hallucinated / len(valid), 4)

def compute_abstention_accuracy(sample3_responses):
    """Fraction of missing clause questions (Sample 3) correctly identified as absent."""
    valid = [r for r in sample3_responses if r and not r.startswith("ERROR:")]
    if not valid:
        return float("nan")
    correct = sum(1 for r in valid if any(ph in r.lower() for ph in ABSTENTION_PHRASES))
    return round(correct / len(valid), 4)

def compute_median_latency(latencies):
    valid = sorted(l for l in latencies if l > 0)
    if not valid:
        return float("nan")
    n = len(valid)
    mid = n // 2
    return valid[mid] if n % 2 == 1 else round((valid[mid - 1] + valid[mid]) / 2.0, 3)

def _safe_mean(lst):
    clean = [x for x in lst if x == x and x is not None]
    if not clean:
        return "N/A"
    return str(round(sum(clean) / len(clean), 4))

def pct(val_str):
    if val_str == "N/A":
        return "N/A"
    try:
        return str(round(float(val_str) * 100, 2))
    except:
        return "N/A"

def compute_table7(system_name, results, questions, ground_truth):
    has_retrieval = system_name != "B1_Ungrounded"
    is_dense = system_name == "P_DenseRAG"
    q_map = {q["qid"]: q for q in questions}

    p7_vals, mrr_vals, top1_vals, faith_vals, cit_vals, latencies = [], [], [], [], [], []
    all_resp, s3_resp = [], []

    for r in results:
        q = q_map.get(r["qid"], {})
        exp = q.get("expected_clauses_present", "")
        resp = r.get("response", "")
        lat = r.get("latency_s", 0.0)
        cid = r.get("contract_id", "")

        all_resp.append(resp)
        latencies.append(lat)
        faith_vals.append(compute_faithfulness(resp))
        cit_vals.append(compute_citation_accuracy(resp))

        if has_retrieval and r.get("retrieved_chunks"):
            p7 = compute_precision_at_k(r["retrieved_chunks"], exp)
            mrr = compute_mrr(r["retrieved_chunks"], exp)
            if p7 == p7:
                p7_vals.append(p7)
            if mrr == mrr:
                mrr_vals.append(mrr)

        top1 = r.get("top1_similarity")
        if is_dense and top1 is not None:
            top1_vals.append(top1)

        if cid == "Sample_3":
            s3_resp.append(resp)

    hall = compute_hallucination_rate(all_resp)
    abst = compute_abstention_accuracy(s3_resp)
    med = compute_median_latency(latencies)

    return {
        "system": system_name,
        "P@7":                    _safe_mean(p7_vals) if has_retrieval else "N/A",
        "MRR":                    _safe_mean(mrr_vals) if has_retrieval else "N/A",
        "Top-1 similarity":       _safe_mean(top1_vals) if is_dense else "N/A",
        "Faithfulness (%)":       pct(_safe_mean(faith_vals)),
        "Citation accuracy (%)":  pct(_safe_mean(cit_vals)) if has_retrieval else "N/A",
        "Hallucination rate (%)": str(round(hall * 100, 2)) if hall == hall else "N/A",
        "Abstention accuracy (%)":str(round(abst * 100, 2)) if abst == abst else "N/A",
        "Median latency (s)":     "N/A" if med != med else str(med),
    }

# ---------------------------------------------------------------------------
# Metric Calculations (Table 8)
# ---------------------------------------------------------------------------

def detect_risk(response, issue_type):
    if not response or response.startswith("ERROR:"):
        return False
    lower = response.lower()
    return any(kw in lower for kw in RISK_KEYWORDS.get(issue_type, []))

def compute_table8(system_name, results, ground_truth, questions):
    by_contract = {}
    for r in results:
        by_contract.setdefault(r["contract_id"], []).append(r)

    ordered_issue_types = [
        "one-sided termination",
        "excessive working hours",
        "broad non-compete",
        "unilateral deductions",
        "missing standard clause"
    ]

    all_cids = set(q["contract_id"] for q in questions)
    per_rows = []
    tot_tp, tot_fp, tot_fn, tot_seeded = 0, 0, 0, 0

    for issue_type in ordered_issue_types:
        gt_recs = [g for g in ground_truth if g["seeded_issue_type"] == issue_type]
        seeded = len(gt_recs)
        tot_seeded += seeded

        tp, fn = 0, 0
        seeded_cids = set()

        for gt in gt_recs:
            cid = gt["contract_id"]
            seeded_cids.add(cid)
            detected = any(detect_risk(r["response"], issue_type) for r in by_contract.get(cid, []))
            if detected:
                tp += 1
            else:
                fn += 1

        fp = 0
        for neg_cid in (all_cids - seeded_cids):
            if any(detect_risk(r["response"], issue_type) for r in by_contract.get(neg_cid, [])):
                fp += 1

        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        rec  = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0

        tot_tp += tp
        tot_fp += fp
        tot_fn += fn

        per_rows.append({
            "Seeded issue type": issue_type.capitalize(),
            "raw_type": issue_type,
            "Seeded": seeded,
            "Detected": tp,
            "FP": fp,
            "FN": fn,
            "Precision": f"{prec * 100:.1f}%",
            "Recall": f"{rec * 100:.1f}%"
        })

    micro_p = round(tot_tp / (tot_tp + tot_fp), 4) if (tot_tp + tot_fp) > 0 else 0.0
    micro_r = round(tot_tp / (tot_tp + tot_fn), 4) if (tot_tp + tot_fn) > 0 else 0.0

    overall = {
        "Seeded issue type": "Overall",
        "raw_type": "Overall",
        "Seeded": tot_seeded,
        "Detected": tot_tp,
        "FP": tot_fp,
        "FN": tot_fn,
        "Precision": f"{micro_p * 100:.1f}%",
        "Recall": f"{micro_r * 100:.1f}%"
    }

    return per_rows, overall

# ---------------------------------------------------------------------------
# Saving Files
# ---------------------------------------------------------------------------

def save_raw_predictions(all_results):
    with open(PREDICTIONS_JSONL, "w", encoding="utf-8") as f:
        for rec in all_results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  SAVED: {len(all_results)} predictions -> {PREDICTIONS_JSONL.name}")

def save_table7(b1_row, b2_row, p_row):
    metrics = [
        "P@7",
        "MRR",
        "Top-1 similarity",
        "Faithfulness (%)",
        "Citation accuracy (%)",
        "Hallucination rate (%)",
        "Abstention accuracy (%)",
        "Median latency (s)"
    ]
    with open(TABLE7_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "B1: Ungrounded", "B2: BM25 + LLM", "P: Proposed RAG"])
        for m in metrics:
            writer.writerow([m, b1_row.get(m, "N/A"), b2_row.get(m, "N/A"), p_row.get(m, "N/A")])
    print(f"  SAVED: {TABLE7_CSV.name}")

def save_table8(per_rows, overall_row):
    fields = ["Seeded issue type", "Seeded", "Detected", "Precision", "Recall"]
    with open(TABLE8_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in per_rows:
            writer.writerow(r)
        writer.writerow(overall_row)
    print(f"  SAVED: {TABLE8_CSV.name}")

def generate_report(t7_b1, t7_b2, t7_p, t8_per, t8_ov, questions, ground_truth):
    lines = [
        "# Evaluation Report: AI Legal Document Assistant",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Model:** gemini-3.1-flash-lite | **Temperature:** {GEMINI_TEMPERATURE} | **Seed:** {RANDOM_SEED}",
        f"**Benchmark Size:** {len(questions)} evaluation questions | **Seeded Risks:** {len(ground_truth)}",
        "",
        "---",
        "",
        "## 1. Table 7: Retrieval and Generation Metrics",
        "",
        "| Metric | B1: Ungrounded | B2: BM25 + LLM | P: Proposed RAG |",
        "|---|---|---|---|",
    ]
    metrics = [
        "P@7",
        "MRR",
        "Top-1 similarity",
        "Faithfulness (%)",
        "Citation accuracy (%)",
        "Hallucination rate (%)",
        "Abstention accuracy (%)",
        "Median latency (s)"
    ]
    for m in metrics:
        lines.append(f"| {m} | {t7_b1.get(m, 'N/A')} | {t7_b2.get(m, 'N/A')} | {t7_p.get(m, 'N/A')} |")

    lines.extend([
        "",
        "### Table 7 Metric Calculation Formulas:",
        "- **P@7 (Precision at 7):** `Relevant_Chunks_in_Top7 / 7`. Evaluated for queries with target clauses in the contract. N/A for B1 (no retrieval).",
        "- **MRR (Mean Reciprocal Rank):** `1 / Rank_of_First_Relevant_Chunk`. N/A for B1 (no retrieval).",
        "- **Top-1 similarity:** Mean cosine similarity of top retrieved chunk. N/A for B1 and B2 (BM25 does not produce cosine similarities).",
        "- **Faithfulness (%):** Percentage of grounded contract citations vs ungrounded generic assertions in the response.",
        "- **Citation accuracy (%):** Percentage of responses containing valid clause/source citations. N/A for B1 (no sources provided).",
        "- **Hallucination rate (%):** Percentage of responses that assert unsubstantiated general conditions without grounding.",
        "- **Abstention accuracy (%):** Accuracy of abstaining on missing clauses (Sample 3).",
        "- **Median latency (s):** Median end-to-end API response time across 15 queries.",
        "",
        "---",
        "",
        "## 2. Table 8: Risk Detection Evaluation (Proposed System)",
        "",
        "| Seeded issue type | Seeded | Detected | Precision | Recall |",
        "|---|---|---|---|---|",
    ])

    for r in t8_per:
        lines.append(f"| {r['Seeded issue type']} | {r['Seeded']} | {r['Detected']} | {r['Precision']} | {r['Recall']} |")
    lines.append(f"| **{t8_ov['Seeded issue type']}** | **{t8_ov['Seeded']}** | **{t8_ov['Detected']}** | **{t8_ov['Precision']}** | **{t8_ov['Recall']}** |")

    lines.extend([
        "",
        "### Table 8 Calculation Methodology:",
        "- **TP (True Positives):** Number of seeded risk instances correctly detected and flagged in the respective contract.",
        "- **FP (False Positives):** Instances where a risk was falsely flagged in a document where it was not present.",
        "- **FN (False Negatives):** Seeded risk instances missed by the model.",
        "- **Precision:** `TP / (TP + FP)`",
        "- **Recall:** `TP / (TP + FN)`",
        "- **Overall (Micro-average):**",
        "  - `Micro-Precision = sum(TP) / (sum(TP) + sum(FP))`",
        "  - `Micro-Recall = sum(TP) / (sum(TP) + sum(FN))`",
        "",
        "---",
        "## 3. Ground Truth Breakdown",
        "- **Sample 1 (Service Agreement):** Balanced baseline contract (0 seeded risks).",
        "- **Sample 2 (Employment Agreement):** 4 high-risk clauses (one-sided termination, excessive hours, broad non-compete, unilateral deductions).",
        "- **Sample 3 (Rental Agreement):** 3 missing clauses (termination notice, deposit refund terms, dispute resolution).",
        "- **Sample 4 (Complex NDA):** 0 risky clauses (used for summarization and clause boundary extraction).",
        "- **Total Seeded Risks:** 7",
    ])

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  SAVED: {REPORT_MD.name}")

# ---------------------------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------------------------

def main():
    _print_section("REPRODUCIBLE EVALUATION PIPELINE")
    print(f"  Working Dir: {ROOT}")
    print(f"  Seed: {RANDOM_SEED} | Temp: {GEMINI_TEMPERATURE} | Top-K: {TOP_K_RETRIEVAL}")

    questions = load_questions()
    ground_truth = load_ground_truth()
    client = init_gemini()
    chroma_col = init_chromadb()
    embed_model = init_embed_model()

    cache = load_checkpoint()
    if cache:
        valid_cached = sum(1 for v in cache.values() if not v.get("response", "").startswith("ERROR:"))
        print(f"  OK: Loaded {valid_cached} previously completed predictions from checkpoint")

    # 1. Run B1
    b1_results = run_b1(questions, client, cache)

    # 2. Run B2
    b2_results = run_b2(questions, client, cache)

    # 3. Run Proposed RAG
    p_results = run_proposed_rag(questions, client, chroma_col, embed_model, cache)

    # Combine all raw predictions
    all_predictions = b1_results + b2_results + p_results
    save_raw_predictions(all_predictions)

    # Compute Table 7
    _print_section("COMPUTING TABLE 7 METRICS")
    t7_b1 = compute_table7("B1_Ungrounded", b1_results, questions, ground_truth)
    t7_b2 = compute_table7("B2_BM25", b2_results, questions, ground_truth)
    t7_p  = compute_table7("P_DenseRAG", p_results, questions, ground_truth)

    save_table7(t7_b1, t7_b2, t7_p)

    # Compute Table 8
    _print_section("COMPUTING TABLE 8 RISK DETECTION METRICS")
    t8_per, t8_ov = compute_table8("P_DenseRAG", p_results, ground_truth, questions)
    save_table8(t8_per, t8_ov)

    # Generate Report
    _print_section("GENERATING EVALUATION REPORT")
    generate_report(t7_b1, t7_b2, t7_p, t8_per, t8_ov, questions, ground_truth)

    # Print Formatted Results to Console
    _print_section("FINAL RESULTS: TABLE 7")
    print(f"  {'Metric':<25} | {'B1: Ungrounded':<15} | {'B2: BM25 + LLM':<15} | {'P: Proposed RAG':<15}")
    print("  " + "-" * 75)
    metrics = [
        "P@7", "MRR", "Top-1 similarity", "Faithfulness (%)",
        "Citation accuracy (%)", "Hallucination rate (%)",
        "Abstention accuracy (%)", "Median latency (s)"
    ]
    for m in metrics:
        print(f"  {m:<25} | {t7_b1.get(m,'N/A'):<15} | {t7_b2.get(m,'N/A'):<15} | {t7_p.get(m,'N/A'):<15}")

    _print_section("FINAL RESULTS: TABLE 8")
    print(f"  {'Seeded issue type':<28} | {'Seeded':<8} | {'Detected':<10} | {'Precision':<10} | {'Recall':<10}")
    print("  " + "-" * 75)
    for r in t8_per:
        print(f"  {r['Seeded issue type']:<28} | {r['Seeded']:<8} | {r['Detected']:<10} | {r['Precision']:<10} | {r['Recall']:<10}")
    print("  " + "-" * 75)
    print(f"  {t8_ov['Seeded issue type']:<28} | {t8_ov['Seeded']:<8} | {t8_ov['Detected']:<10} | {t8_ov['Precision']:<10} | {t8_ov['Recall']:<10}")

    _print_section("EVALUATION PIPELINE COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    main()
