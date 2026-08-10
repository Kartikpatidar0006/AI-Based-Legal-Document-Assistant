"""
Week 3 - Stage 2: Embedding Generation & ChromaDB Storage
AI-Based Legal Document Assistant for Small Businesses

This script loads all chunks from data/chunks/all_chunks.json,
generates dense vector embeddings for each chunk using the
sentence-transformers model 'all-MiniLM-L6-v2', and stores the
embeddings (along with text + metadata) in a local ChromaDB
persistent collection at data/vector_db/.

Metadata stored per chunk: filename, category, chunk_id, chunk_index
This lets you later filter searches (e.g., only within compliance_docs).

Usage:
    python embed_and_store.py

Dependencies (not already in requirements.txt):
    pip install chromadb sentence-transformers
    (Both are already listed in requirements.txt for this project)
"""

import json
import sys
from pathlib import Path

# Force UTF-8 output so emoji print correctly on Windows (cp1252 terminal)
sys.stdout.reconfigure(encoding="utf-8")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
CHUNKS_JSON: Path = Path("data/chunks/all_chunks.json")
VECTOR_DB_PATH: Path = Path("data/vector_db")          # ChromaDB will persist here
COLLECTION_NAME: str = "legal_docs"                     # name of our ChromaDB collection
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"              # 384-dim, fast and accurate

# ChromaDB's add() has a max batch size; split large inputs to stay safe
BATCH_SIZE: int = 100


def load_chunks(json_path: Path) -> list[dict]:
    """
    Load the list of chunk records from all_chunks.json.
    Raises FileNotFoundError if the file is missing (run chunking.py first).
    """
    if not json_path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {json_path}\n"
            "Please run chunking.py first."
        )

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"✅ Loaded {len(chunks)} chunks from {json_path}")
        return chunks
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from {json_path}: {e}")


def get_or_create_collection(db_path: Path, collection_name: str) -> chromadb.Collection:
    """
    Initialise a ChromaDB PersistentClient at db_path and return (or create)
    the named collection. The collection uses ChromaDB's default cosine-distance
    HNSW index — suitable for semantic similarity search.
    """
    db_path.mkdir(parents=True, exist_ok=True)

    # PersistentClient automatically saves data to disk between runs
    client = chromadb.PersistentClient(path=str(db_path))

    # get_or_create_collection is idempotent — safe to re-run
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},   # cosine similarity for text embeddings
    )
    print(f"📦 ChromaDB collection '{collection_name}' ready  (path: {db_path})")
    return collection


def embed_and_store(chunks: list[dict], collection: chromadb.Collection) -> None:
    """
    For every chunk:
      1. Generate a 384-dim embedding with all-MiniLM-L6-v2
      2. Upsert it into ChromaDB along with text + metadata

    Uses upsert (not add) so re-running the script is safe — existing
    vectors with the same chunk_id are simply overwritten.
    """
    print(f"\n🤖 Loading embedding model: {EMBEDDING_MODEL} …")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("   Model loaded. Generating embeddings …\n")

    total = len(chunks)

    # Process in batches to avoid memory spikes with large corpora
    for batch_start in range(0, total, BATCH_SIZE):
        batch = chunks[batch_start : batch_start + BATCH_SIZE]
        batch_end = min(batch_start + BATCH_SIZE, total)

        texts: list[str] = [c["text"] for c in batch]

        # Generate embeddings — returns a numpy array of shape (N, 384)
        # convert_to_list=True gives us plain Python lists, required by ChromaDB
        embeddings: list[list[float]] = model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()

        # Build ChromaDB-compatible lists
        ids: list[str] = [c["chunk_id"] for c in batch]
        metadatas: list[dict] = [
            {
                "filename": c["filename"],
                "category": c["category"],
                "chunk_index": c["chunk_index"],
                "source_path": c.get("source_path", ""),
            }
            for c in batch
        ]

        try:
            # upsert overwrites if chunk_id already exists — idempotent
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
        except Exception as e:
            print(f"  ❌ Failed to upsert batch [{batch_start}:{batch_end}]: {e}")
            continue

        print(f"  ✅ Stored chunks {batch_start + 1:>4} – {batch_end:>4}  /  {total}")

    print(f"\n💾 All done! Vectors persisted at: {VECTOR_DB_PATH}")


def main() -> None:
    print("=" * 55)
    print("  STAGE 2 — EMBEDDING & VECTOR STORAGE")
    print("=" * 55)

    # Step 1: Load chunks
    try:
        chunks = load_chunks(CHUNKS_JSON)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ ERROR: {e}")
        return

    if not chunks:
        print("❌ Chunks list is empty. Please re-run chunking.py.")
        return

    # Step 2: Connect to / create ChromaDB collection
    try:
        collection = get_or_create_collection(VECTOR_DB_PATH, COLLECTION_NAME)
    except Exception as e:
        print(f"\n❌ ChromaDB initialisation failed: {e}")
        return

    # Step 3: Generate embeddings + store vectors
    try:
        embed_and_store(chunks, collection)
    except Exception as e:
        print(f"\n❌ Embedding/storage failed: {e}")
        return

    # Step 4: Verify final count
    stored_count = collection.count()
    print(f"\n{'=' * 55}")
    print(f"  STORAGE SUMMARY")
    print(f"{'=' * 55}")
    print(f"  Vectors in collection : {stored_count}")
    print(f"  Embedding model       : {EMBEDDING_MODEL}")
    print(f"  Collection name       : {COLLECTION_NAME}")
    print(f"  DB location           : {VECTOR_DB_PATH}")
    print(f"{'=' * 55}")
    print(f"\n✅ Done! Next step: run  python query_test.py")


if __name__ == "__main__":
    main()
