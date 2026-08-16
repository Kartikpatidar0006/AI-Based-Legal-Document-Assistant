"""
Week 4 - RAG Generation Pipeline
AI-Based Legal Document Assistant for Small Businesses

─────────────────────────────────────────────────────────────────
WHERE THIS FITS IN THE OVERALL PIPELINE
─────────────────────────────────────────────────────────────────
  Week 2 → week2_text_extraction.py
            PDFs → plain text → all_documents.json

  Week 3 → chunking.py        text → 242 overlapping chunks
         → embed_and_store.py  chunks → 384-dim vectors → ChromaDB

  Week 4 → THIS FILE (rag_pipeline.py)
            query → embed → retrieve chunks → build prompt
            → Gemini API → structured answer with citations

─────────────────────────────────────────────────────────────────
HOW TO RUN
─────────────────────────────────────────────────────────────────
  Interactive CLI:
      python rag_pipeline.py
      python rag_pipeline.py --category compliance_docs
      python rag_pipeline.py --top-k 7

  Import from FastAPI (next step):
      from rag_pipeline import answer_query
      result = answer_query("What is GST registration process?")

─────────────────────────────────────────────────────────────────
.env REQUIRED:
    GOOGLE_API_KEY=your_gemini_api_key_here
  OR
    GEMINI_API_KEY=your_gemini_api_key_here
─────────────────────────────────────────────────────────────────

Dependencies:
    pip install google-genai python-dotenv chromadb sentence-transformers
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — keep these in sync with embed_and_store.py / query_test.py
# ─────────────────────────────────────────────────────────────────────────────
VECTOR_DB_PATH: Path = Path("data/vector_db")
COLLECTION_NAME: str = "legal_docs"
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
GEMINI_MODEL: str = "gemini-3.6-flash"          # fast, highly capable reasoning model
DEFAULT_TOP_K: int = 7                           # higher chunk retrieval depth for richer context

# Legal disclaimer — must appear verbatim at the end of every answer
LEGAL_DISCLAIMER: str = (
    "This is general information, not legal advice. "
    "Please consult a qualified legal professional for decisions specific to your business."
)


# ─────────────────────────────────────────────────────────────────────────────
# SETUP — load API key, initialise clients (done once, reused across queries)
# ─────────────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    """
    Load the Gemini API key from the .env file.
    Supports both GOOGLE_API_KEY and GEMINI_API_KEY variable names.
    Raises EnvironmentError with a helpful message if neither is found.
    """
    load_dotenv(override=True)  # reads .env and overrides any stale system env vars

    # Support both naming conventions, prioritizing GEMINI_API_KEY from .env
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "Gemini API key not found!\n"
            "Please add one of these to your .env file:\n"
            "  GOOGLE_API_KEY=your_key_here\n"
            "  GEMINI_API_KEY=your_key_here\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )

    # Sync OS environment variables so SDK consistently uses the newly loaded key
    os.environ["GEMINI_API_KEY"] = api_key
    os.environ["GOOGLE_API_KEY"] = api_key
    return api_key


def init_chromadb() -> "chromadb.Collection":
    """
    Connect to the existing persistent ChromaDB store and return the
    legal_docs collection. Fails clearly if embed_and_store.py hasn't been run.
    """
    import chromadb  # local import so missing package gives a clear error

    if not VECTOR_DB_PATH.exists():
        raise FileNotFoundError(
            f"Vector DB not found at: {VECTOR_DB_PATH}\n"
            "Please run embed_and_store.py first."
        )

    client = chromadb.PersistentClient(path=str(VECTOR_DB_PATH))

    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in existing:
        raise ValueError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found.\n"
            "Please run embed_and_store.py first."
        )

    return client.get_collection(name=COLLECTION_NAME)


def init_embedding_model() -> "SentenceTransformer":
    """Load the sentence-transformer embedding model (cached after first download)."""
    from sentence_transformers import SentenceTransformer  # local import
    return SentenceTransformer(EMBEDDING_MODEL)


def init_gemini(api_key: str) -> "genai.Client":
    """
    Initialise the new google-genai SDK Client.
    The Client holds the API key and is reused for all requests.
    """
    from google import genai  # local import — new SDK (google-genai package)
    return genai.Client(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# RETRIEVAL — embed query and pull top-K chunks from ChromaDB
# ─────────────────────────────────────────────────────────────────────────────

def embed_query(query: str, model: "SentenceTransformer") -> list[float]:
    """
    Embed the user's query using the same model used at index time.
    Returns a list of floats (384 dimensions) that ChromaDB can query against.
    """
    vector = model.encode(query, convert_to_numpy=True)
    return vector.tolist()


def retrieve_chunks(
    query_embedding: list[float],
    collection: "chromadb.Collection",
    top_k: int = DEFAULT_TOP_K,
    category_filter: str | None = None,
) -> list[dict]:
    """
    Query ChromaDB and return top-K most similar chunks as a list of dicts.

    Each dict contains:
        text            – the chunk text
        filename        – source PDF filename
        category        – templates / compliance_docs / sample_contracts
        chunk_index     – position within the document
        similarity      – cosine similarity score (0.0 to 1.0)

    ChromaDB cosine distance is [0, 2]; we convert: similarity = 1 - dist/2
    so 1.0 = perfect match, 0.0 = completely unrelated.
    """
    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if category_filter:
        query_kwargs["where"] = {"category": {"$eq": category_filter}}

    raw = collection.query(**query_kwargs)

    chunks: list[dict] = []
    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]

    for doc_text, meta, dist in zip(docs, metas, dists):
        chunks.append(
            {
                "text": doc_text,
                "filename": meta.get("filename", "unknown"),
                "category": meta.get("category", "unknown"),
                "chunk_index": meta.get("chunk_index", 0),
                "similarity": round(1.0 - dist / 2.0, 4),
            }
        )

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    """
    Construct the full prompt to send to Gemini.

    Structure:
        [System instruction]
        [Numbered context blocks with source labels]
        [User question]
        [Output instructions including citation + disclaimer requirements]

    This function is kept separate so it can be unit-tested independently
    and reused / tweaked when wiring into FastAPI.
    """
    # ── System instruction ────────────────────────────────────────────────────
    system_instruction = (
        "You are an AI Legal Document Assistant designed to help small businesses "
        "in India understand legal documents, contracts, and compliance requirements.\n\n"
        "STRICT RULES:\n"
        "1. Answer ONLY using the information provided in the Context Sections below.\n"
        "2. Do NOT invent, assume, or add any information that is not present in the context.\n"
        "3. If the context does not contain enough information to answer the question, "
        "say exactly: \"I don't have enough information in the provided documents to answer this question.\"\n"
        "4. Always cite the specific source document(s) you used in your answer.\n"
        "5. Your answer must end with the exact disclaimer provided at the end of this prompt.\n"
        "6. Write in clear, simple English that a non-lawyer small business owner can understand.\n"
    )

    # ── Context blocks ────────────────────────────────────────────────────────
    context_lines: list[str] = ["─" * 60, "CONTEXT SECTIONS (retrieved from knowledge base):", "─" * 60]

    for i, chunk in enumerate(retrieved_chunks, start=1):
        source_label = f"[Source {i}: {chunk['filename']} | {chunk['category']} | similarity: {chunk['similarity']}]"
        context_lines.append(f"\n{source_label}")
        context_lines.append(chunk["text"])
        context_lines.append("")  

    context_lines.append("─" * 60)
    context_block = "\n".join(context_lines)

    # ── Output instructions ───────────────────────────────────────────────────
    output_instructions = (
        "\nINSTRUCTIONS FOR YOUR RESPONSE:\n"
        "- Provide a clear, structured answer to the question below.\n"
        "- After your answer, add a 'Sources Used' section listing which source numbers "
        "and filenames you referenced.\n"
        f"- End your response with this exact disclaimer on its own line:\n"
        f"  \"{LEGAL_DISCLAIMER}\"\n"
    )

    # ── Final assembled prompt ────────────────────────────────────────────────
    prompt = (
        f"{system_instruction}\n"
        f"{context_block}\n"
        f"{output_instructions}\n"
        f"USER QUESTION: {query}\n\n"
        f"YOUR ANSWER:"
    )

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# GENERATION — call Gemini API
# ─────────────────────────────────────────────────────────────────────────────

def call_gemini(
    prompt: str,
    gemini_client: "genai.Client",
    max_retries: int = 2,
) -> str:
    """
    Send the prompt to Gemini using the new google-genai SDK and return the
    response text.

    Handles rate limit errors (429) with a simple retry + back-off.
    Other errors are caught and returned as a human-readable string
    so the CLI doesn't crash mid-session.
    """
    from google import genai  # local import
    from google.genai import types

    candidate_models = [GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-flash-latest", "gemini-3.5-flash"]
    
    last_error = None
    for attempt in range(1, max_retries + 2):  
        for model_name in candidate_models:
            try:
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                    )
                )
                return response.text
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # If model is deprecated/not found (404) or server unavailable (503/500/high demand), try next model
                if any(err in error_str for err in ["404", "not_found", "not found", "503", "unavailable", "500", "overloaded"]):
                    continue
                
                # Invalid API key (400)
                if "api_key_invalid" in error_str or "api key not valid" in error_str:
                    return (
                        "❌ Invalid Gemini API key!\n"
                        "Please check your GEMINI_API_KEY in the .env file.\n"
                        "Get a valid key at: https://aistudio.google.com/app/apikey"
                    )

                # Rate limit — wait and retry
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    wait_seconds = 15 * attempt 
                    if attempt <= max_retries:
                        print(
                            f"\n⚠️  Gemini rate limit hit (attempt {attempt}/{max_retries + 1}). "
                            f"Waiting {wait_seconds}s before retry..."
                        )
                        time.sleep(wait_seconds)
                        break
                    else:
                        return (
                            "❌ Gemini rate limit exceeded after retries. "
                            "You are on the free tier — please wait 1 minute and try again."
                        )

                # Safety filter — content was blocked
                if "block" in error_str or "safety" in error_str or "finish_reason" in error_str:
                    return (
                        "❌ Gemini blocked this response due to safety filters. "
                        "Try rephrasing your question."
                    )

                # Any other error
                return (
                    f"❌ Gemini API error: {type(e).__name__}: {e}\n"
                    "Please check your API key and internet connection."
                )

    return f"❌ Gemini did not return a response: {last_error}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC FUNCTION — import this from FastAPI
# ─────────────────────────────────────────────────────────────────────────────

# Module-level singletons — initialised once on first call, reused after
_collection = None
_embed_model = None
_gemini_model = None


def _get_clients() -> tuple:
    """
    Lazily initialise and cache ChromaDB, embedding model, and Gemini model.
    This pattern is safe for both CLI and FastAPI usage — the heavy models
    are loaded only once per process, not on every request.
    """
    global _collection, _embed_model, _gemini_model

    if _collection is None:
        _collection = init_chromadb()

    if _embed_model is None:
        print("🤖 Loading embedding model (first run only)...")
        _embed_model = init_embedding_model()
        print("   Embedding model ready.")

    if _gemini_model is None:
        api_key = load_api_key()
        _gemini_model = init_gemini(api_key)

    return _collection, _embed_model, _gemini_model


# ─────────────────────────────────────────────────────────────────────────────
# SHARED PUBLIC HELPERS — importable by document_processor.py
# ─────────────────────────────────────────────────────────────────────────────

def get_clients() -> tuple:
    """
    Public alias for _get_clients().
    Import this from document_processor.py (or any future module) to reuse
    the already-cached ChromaDB collection, embedding model, and Gemini client
    without re-initialising them.

    Returns:
        (collection, embed_model, gemini_client)  — same tuple as _get_clients()
    """
    return _get_clients()


def retrieve_chunks_for_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category_filter: str | None = None,
) -> list[dict]:
    """
    Convenience public function: embed a query string and retrieve top-K chunks.

    This wraps embed_query() + retrieve_chunks() so that document_processor.py
    can call a single function for RAG retrieval without managing the
    embedding model or ChromaDB collection directly.

    Args:
        query           – Natural language query / topic string.
        top_k           – Number of chunks to retrieve.
        category_filter – Optional category filter (templates / compliance_docs /
                          sample_contracts).

    Returns:
        List of chunk dicts with keys: text, filename, category, chunk_index, similarity.
        Returns [] if ChromaDB is empty or unavailable.
    """
    try:
        collection, embed_model, _ = _get_clients()
        query_embedding = embed_query(query, embed_model)
        return retrieve_chunks(query_embedding, collection, top_k=top_k,
                               category_filter=category_filter)
    except Exception as exc:
        # Don't crash the caller — return empty list with a print so it's visible
        print(f"  ⚠️  retrieve_chunks_for_query failed: {exc}")
        return []


def answer_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category_filter: str | None = None,
) -> dict:
    """
    Full RAG pipeline: retrieve → prompt → generate → return structured result.

    This is the PRIMARY PUBLIC API of this module.
    Import and call this directly from your FastAPI backend:

        from rag_pipeline import answer_query

        @app.post("/query")
        async def query_endpoint(request: QueryRequest):
            return answer_query(request.question, top_k=5)

    Args:
        query           – The user's natural language question
        top_k           – Number of chunks to retrieve (default 5)
        category_filter – Optional: restrict to 'templates', 'compliance_docs',
                          or 'sample_contracts'

    Returns a dict:
        {
            "query":        str,
            "answer":       str,
            "sources":      [{"filename": str, "category": str, "similarity_score": float}],
            "chunks_used":  int,
            "model":        str
        }
    """
    if not query or not query.strip():
        return {
            "query": query,
            "answer": "Please provide a non-empty question.",
            "sources": [],
            "chunks_used": 0,
            "model": GEMINI_MODEL,
        }

    # Step 1: Get cached clients
    collection, embed_model, gemini_model = _get_clients()

    # Step 2: Embed query
    query_embedding = embed_query(query, embed_model)

    # Step 3: Retrieve top-K chunks
    chunks = retrieve_chunks(query_embedding, collection, top_k=top_k, category_filter=category_filter)

    if not chunks:
        return {
            "query": query,
            "answer": "No relevant documents found in the knowledge base for this query.",
            "sources": [],
            "chunks_used": 0,
            "model": GEMINI_MODEL,
        }

    # Step 4: Build prompt
    prompt = build_prompt(query, chunks)

    # Step 5: Call Gemini (gemini_model is actually a genai.Client in new SDK)
    answer_text = call_gemini(prompt, gemini_model)

    # Step 6: Build structured response
    sources = [
        {
            "filename": c["filename"],
            "category": c["category"],
            "similarity_score": c["similarity"],
        }
        for c in chunks
    ]

    return {
        "query": query,
        "answer": answer_text,
        "sources": sources,
        "chunks_used": len(chunks),
        "model": GEMINI_MODEL,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI — pretty-print the answer when run directly
# ─────────────────────────────────────────────────────────────────────────────

def print_answer(result: dict) -> None:
    """Pretty-print a structured answer dict to the terminal."""
    print("\n" + "═" * 70)
    print(f"  QUERY: {result['query']}")
    print("═" * 70)

    print("\n📋 ANSWER:\n")
    print(result["answer"])

    print("\n" + "─" * 70)
    print(f"  Sources retrieved ({result['chunks_used']} chunks):")
    for i, src in enumerate(result["sources"], start=1):
        print(f"    {i}. {src['filename']}  [{src['category']}]  "
              f"similarity: {src['similarity_score']:.4f}")

    print(f"\n  Model: {result['model']}")
    print("─" * 70 + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Legal Document Assistant — RAG Generation Pipeline (Week 4)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Restrict retrieval to a specific category: "
             "templates | compliance_docs | sample_contracts",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        dest="top_k",
        help=f"Number of chunks to retrieve per query (default: {DEFAULT_TOP_K})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 70)
    print("  WEEK 4 — RAG PIPELINE  (Retrieval + Generation via Gemini)")
    print("=" * 70)

    # Validate API key up-front before entering the loop
    try:
        api_key = load_api_key()
        print(f"✅ API key loaded  |  model: {GEMINI_MODEL}")
    except EnvironmentError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # Initialise all clients (ChromaDB + embedding model + Gemini)
    try:
        collection, embed_model, gemini_model = _get_clients()
        total = collection.count()
        print(f"✅ ChromaDB ready  |  {total} vectors indexed")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Startup error: {e}")
        sys.exit(1)

    if args.category:
        print(f"🔍 Category filter: only searching within '{args.category}'")

    print(f"\nType your question. Type 'exit' to quit.\n")

    while True:
        try:
            query = input("❓ Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not query:
            print("  ⚠️  Empty input — please type a question.\n")
            continue

        if query.lower() in {"exit", "quit", "q"}:
            print("Goodbye! 👋")
            break

        print("\n⏳ Retrieving and generating answer...\n")

        try:
            result = answer_query(
                query=query,
                top_k=args.top_k,
                category_filter=args.category,
            )
            print_answer(result)
        except Exception as e:
            print(f"\n❌ Unexpected error: {type(e).__name__}: {e}\n")
            continue


if __name__ == "__main__":
    main()
