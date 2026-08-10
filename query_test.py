"""
Week 3 - Stage 3: Retrieval Query Test (CLI)
AI-Based Legal Document Assistant for Small Businesses

A lightweight CLI script for MANUALLY TESTING retrieval quality
before hooking up any LLM generation step.

It:
  1. Accepts a natural language question from the user (stdin)
  2. Embeds the query using the same all-MiniLM-L6-v2 model used at index time
  3. Queries ChromaDB for the top-5 most semantically similar chunks
  4. Prints each result with its rank, similarity score, source filename,
     category, and a text preview

No LLM calls are made — this is pure retrieval testing.

Optional: pass --category <name> to restrict search to a specific category
  e.g.  python query_test.py --category compliance_docs

Usage:
    python query_test.py
    python query_test.py --category templates
    python query_test.py --category compliance_docs

Dependencies:
    pip install chromadb sentence-transformers
"""

import argparse
import sys
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

import chromadb
from sentence_transformers import SentenceTransformer

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — must match embed_and_store.py
# ─────────────────────────────────────────────────────────────────────────────
VECTOR_DB_PATH: Path = Path("data/vector_db")
COLLECTION_NAME: str = "legal_docs"
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

TOP_K: int = 5                    # number of results to retrieve
PREVIEW_LENGTH: int = 300         # characters of chunk text to display


def load_collection() -> chromadb.Collection:
    """
    Connect to the existing ChromaDB persistent store and return the
    legal_docs collection. Raises an error if the DB or collection
    is not found (i.e. embed_and_store.py hasn't been run yet).
    """
    if not VECTOR_DB_PATH.exists():
        raise FileNotFoundError(
            f"Vector DB not found at: {VECTOR_DB_PATH}\n"
            "Please run embed_and_store.py first."
        )

    client = chromadb.PersistentClient(path=str(VECTOR_DB_PATH))

    # list_collections returns collection names as strings
    existing = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in existing:
        raise ValueError(
            f"Collection '{COLLECTION_NAME}' not found in ChromaDB.\n"
            "Please run embed_and_store.py first."
        )

    collection = client.get_collection(name=COLLECTION_NAME)
    return collection


def embed_query(query: str, model: SentenceTransformer) -> list[float]:
    """
    Convert the user's natural language query into a 384-dim embedding
    using the same model that was used during indexing. This ensures
    the query vector lives in the same embedding space as the stored chunks.
    """
    vector = model.encode(query, convert_to_numpy=True)
    return vector.tolist()


def retrieve(
    query_embedding: list[float],
    collection: chromadb.Collection,
    top_k: int = TOP_K,
    category_filter: str | None = None,
) -> dict:
    """
    Query ChromaDB for the top-k most similar chunks.

    If category_filter is provided, restricts the search to chunks whose
    'category' metadata field matches (e.g. "compliance_docs").

    ChromaDB returns distances in [0, 2] for cosine space (0 = identical).
    We convert to a similarity score: similarity = 1 - distance/2
    so that 1.0 = perfect match and 0.0 = completely dissimilar.
    """
    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    # Apply metadata filter if a category was requested
    if category_filter:
        query_kwargs["where"] = {"category": {"$eq": category_filter}}

    results = collection.query(**query_kwargs)
    return results


def print_results(results: dict, query: str, category_filter: str | None) -> None:
    """
    Pretty-print the retrieval results in a readable CLI format.
    """
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        print("\n⚠️  No results found. Try a different query or check your vector DB.")
        return

    # Header
    print("\n" + "═" * 65)
    print(f"  QUERY : {query}")
    if category_filter:
        print(f"  FILTER: category = {category_filter}")
    print(f"  TOP-{len(documents)} RESULTS")
    print("═" * 65)

    for rank, (doc_text, meta, dist) in enumerate(
        zip(documents, metadatas, distances), start=1
    ):
        # Convert cosine distance → similarity score (0-1 range)
        # ChromaDB cosine distance is in [0, 2]; 0 = perfect match
        similarity = round(1.0 - dist / 2.0, 4)

        filename = meta.get("filename", "unknown")
        category = meta.get("category", "unknown")
        chunk_index = meta.get("chunk_index", "?")

        # Truncate text for display
        preview = doc_text[:PREVIEW_LENGTH].replace("\n", " ").strip()
        if len(doc_text) > PREVIEW_LENGTH:
            preview += " …"

        print(f"\n  ┌─ Rank #{rank}")
        print(f"  │  Similarity Score : {similarity:.4f}")
        print(f"  │  Source File      : {filename}")
        print(f"  │  Category         : {category}")
        print(f"  │  Chunk Index      : {chunk_index}")
        print(f"  │  Preview          :")
        print(f"  │    {preview}")
        print(f"  └{'─' * 60}")

    print()


def parse_args() -> argparse.Namespace:
    """Parse optional CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Test ChromaDB retrieval quality for the Legal Doc Assistant."
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help=(
            "Restrict search to a specific category: "
            "templates | compliance_docs | sample_contracts"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    category_filter: str | None = args.category

    print("=" * 65)
    print("  STAGE 3 — RETRIEVAL QUERY TEST  (no LLM)")
    print("=" * 65)

    # Step 1: Load ChromaDB collection
    try:
        collection = load_collection()
        total_vectors = collection.count()
        print(f"✅ Connected to ChromaDB  |  {total_vectors} vectors indexed")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

    # Step 2: Load embedding model (reuse across queries in the same session)
    print(f"🤖 Loading embedding model: {EMBEDDING_MODEL} …")
    try:
        model = SentenceTransformer(EMBEDDING_MODEL)
    except Exception as e:
        print(f"\n❌ Failed to load embedding model: {e}")
        sys.exit(1)

    print("   Model ready.\n")

    if category_filter:
        print(f"🔍 Category filter active: only searching within '{category_filter}'")

    # ─────────────────────────────────────────────────────────────────────────
    # Interactive query loop — keeps running until the user types 'exit'
    # ─────────────────────────────────────────────────────────────────────────
    print("Type your question below. Type 'exit' or press Ctrl+C to quit.\n")

    while True:
        try:
            query = input("❓ Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not query:
            print("  ⚠️  Empty query — please type something.\n")
            continue

        if query.lower() in {"exit", "quit", "q"}:
            print("Goodbye! 👋")
            break

        # Step 3: Embed the query
        try:
            query_embedding = embed_query(query, model)
        except Exception as e:
            print(f"  ❌ Embedding failed: {e}\n")
            continue

        # Step 4: Retrieve top-K chunks from ChromaDB
        try:
            results = retrieve(query_embedding, collection, top_k=TOP_K, category_filter=category_filter)
        except Exception as e:
            print(f"  ❌ Retrieval failed: {e}\n")
            continue

        # Step 5: Display results
        print_results(results, query, category_filter)


if __name__ == "__main__":
    main()
