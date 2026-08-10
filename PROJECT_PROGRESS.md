# 🏛️ AI-Based Legal Document Assistant for Small Businesses
## Project Progress Summary — College Major Project

> **Tech Stack:** Python · FastAPI · React · PostgreSQL · LangChain · ChromaDB · Sentence Transformers · Gemini API · Docker

---

## 🎯 Project Ka Goal Kya Hai?

Ek AI-powered assistant banana jo **small businesses** ki help kare:
- Legal documents **generate** karne mein (NDA, Service Agreement, etc.)
- Documents **review** karne mein (risky clauses pakadna)
- Compliance rules **samjhane** mein (GST, MSME, Labour Law, etc.)
- Documents ke baare mein **natural language mein sawaal** poochna

Is system ka core engine hai **RAG (Retrieval-Augmented Generation)** —
matlab pehle relevant documents dhundo, phir AI se answer generate karo.

---

## 📁 Project Folder Structure

```
AI_Bassed_Legal_Doc_Major_Project/
│
├── data/
│   ├── templates/          ← 5 blank contract templates (PDF)
│   │   ├── NDA Template
│   │   ├── Service Agreement
│   │   ├── Employment Agreement
│   │   ├── Rental Agreement
│   │   └── Partnership Deed
│   │
│   ├── compliance_docs/    ← 5 Indian compliance documents (PDF)
│   │   ├── GST Registration Basics
│   │   ├── MSME Udyam Registration
│   │   ├── Startup India Registration
│   │   ├── Labour Law Compliance
│   │   └── Shop & Establishment Act
│   │
│   ├── sample_contracts/   ← 4 test contracts (fair + risky mix)
│   │   ├── Sample 1 — Balanced Service Agreement (fair)
│   │   ├── Sample 2 — Risky Employment Contract (intentionally risky)
│   │   ├── Sample 3 — Rental with Missing Clauses (incomplete)
│   │   └── Sample 4 — Complex NDA Long (for summarization testing)
│   │
│   ├── extracted_text/     ← Week 2 ka output
│   │   ├── *.txt           (har PDF ka plain text)
│   │   └── all_documents.json  (sab documents ek JSON mein)
│   │
│   ├── chunks/             ← Week 3 ka output
│   │   └── all_chunks.json (242 overlapping text chunks)
│   │
│   └── vector_db/          ← Week 3 ka output
│       └── (ChromaDB files — 242 embedding vectors stored)
│
├── week2_text_extraction.py   ← Week 2 script
├── chunking.py                ← Week 3 script
├── embed_and_store.py         ← Week 3 script
├── query_test.py              ← Week 3 script
├── db_schema.sql              ← Week 3 SQL schema
├── requirements.txt           ← all Python dependencies
└── PROJECT_PROGRESS.md        ← yahi file hai!
```

---

## 📅 Week-by-Week Progress

---

### ✅ WEEK 1 — Project Setup & Planning

**Kya kiya:**
- Project ka idea decide kiya — *AI-Based Legal Document Assistant*
- Tech stack choose kiya (Python, FastAPI, React, PostgreSQL, LangChain, Gemini)
- GitHub repo banaya, folder structure design kiya
- Knowledge base collect kiya:
  - 5 legal templates (PDF format)
  - 5 Indian compliance documents (PDF format)
  - 4 sample test contracts (kuch fair, kuch intentionally risky)

**Output:** Organized `data/` folder with 14 PDFs ready

---

### ✅ WEEK 2 — Text Extraction Pipeline

**Script:** `week2_text_extraction.py`

**Kya kiya:**
- PyMuPDF (fitz) library se sabhi 14 PDFs ka text extract kiya
- Text clean kiya (extra spaces, blank lines hataaye)
- Har document ka ek alag `.txt` file banaya
- Sab documents ko ek combined `all_documents.json` mein save kiya

**all_documents.json ka structure:**
```json
{
  "filename": "01_NDA_Template.pdf",
  "category": "templates",
  "source_path": "data/templates/01_NDA_Template.pdf",
  "char_count": 4200,
  "text": "full extracted text..."
}
```

**Output:**
- `data/extracted_text/` mein 14 `.txt` files
- `data/extracted_text/all_documents.json` — sab documents combined

---

### ✅ WEEK 3 — RAG Pipeline (Chunking + Embeddings + Vector DB)

**Yahi is session mein hua — 4 cheezein banai:**

---

#### 🔪 Stage 1 — `chunking.py` — Document Chunking

**Problem:** Ek poora document ek saath AI ko dena theek nahi hota —
too long, too much noise. Solution: documents ko **chhote pieces** mein todna.

**Kaise kaam karta hai:**
1. `all_documents.json` padha
2. Har document ka text LangChain ke `RecursiveCharacterTextSplitter` se toda
3. Settings:
   - **Chunk size:** 700 characters (ek chunk mein roughly ek paragraph)
   - **Overlap:** 100 characters (chunks ke beech thoda common text — context nahi toota)
4. Har chunk ke saath metadata preserve kiya (filename, category, chunk_index)
5. `data/chunks/all_chunks.json` mein save kiya

**Result:**
```
Total chunks created  : 242
Average chunk size    : 546 characters
Chunks per category:
  • compliance_docs   →  24 chunks
  • sample_contracts  →  22 chunks
  • templates         → 196 chunks
```

**Chunk ka structure:**
```json
{
  "chunk_id": "01_NDA_Template__chunk0",
  "text": "...chunk text...",
  "filename": "01_NDA_Template.pdf",
  "category": "templates",
  "chunk_index": 0,
  "source_path": "data/templates/01_NDA_Template.pdf"
}
```

---

#### 🤖 Stage 2 — `embed_and_store.py` — Embeddings + ChromaDB

**Problem:** Text ko directly compare nahi kar sakte. AI ke liye hume
text ko **numbers (vectors)** mein convert karna hota hai.

**Embedding kya hoti hai?**
> Har text chunk ko ek 384-dimensional vector mein convert karo.
> Similar meaning ke chunks ke vectors bhi similar hote hain.
> Yahi semantic search ka foundation hai.

**Kaise kaam karta hai:**
1. `all_chunks.json` se 242 chunks load kiye
2. `sentence-transformers` model **`all-MiniLM-L6-v2`** use kiya (fast, accurate, free)
3. Har chunk ke liye ek 384-dimension embedding generate ki
4. ChromaDB (local vector database) mein store kiya:
   - Embedding vector
   - Original chunk text
   - Metadata (filename, category, chunk_index)
5. Database path: `data/vector_db/`

**Result:**
```
Vectors in collection : 242
Embedding model       : all-MiniLM-L6-v2
Collection name       : legal_docs
DB location           : data/vector_db/
```

---

#### 🔍 Stage 3 — `query_test.py` — Retrieval Testing (No LLM)

**Purpose:** Yeh sirf testing ke liye hai — verify karna ki
hamare retrieved chunks actually relevant hain ya nahi.
**(Abhi koi LLM call nahi hota — sirf retrieval test)**

**Kaise kaam karta hai:**
1. User se natural language question lo
2. Same model se query ko embed karo
3. ChromaDB mein top-5 most similar chunks dhundo
4. Result print karo: rank, similarity score, source file, preview

**Extra feature:** `--category` flag se sirf ek category mein search karo:
```bash
python query_test.py --category compliance_docs
python query_test.py --category templates
```

**Test result — Query: "What are the key clauses in an NDA agreement?"**

| Rank | Score  | Source File                      | Category         |
|------|--------|----------------------------------|------------------|
| #1   | 0.8208 | Sample_4_Complex_NDA_Long.pdf    | sample_contracts |
| #2   | 0.7830 | Services-Agreement-Kickstart.pdf | templates        |
| #3   | 0.7699 | Sample_4_Complex_NDA_Long.pdf    | sample_contracts |
| #4   | 0.7683 | Services-Agreement-Kickstart.pdf | templates        |
| #5   | 0.7623 | Services-Agreement-Kickstart.pdf | templates        |

✅ **Retrieval quality excellent** — sahi documents top pe aa rahe hain!

---

#### 🗄️ Stage 4 — `db_schema.sql` — PostgreSQL Database Schema

**6 tables banaye with full indexes, foreign keys, comments:**

| Table | Purpose |
|---|---|
| `users` | Registered business owners |
| `documents` | Uploaded legal documents per user |
| `document_chunks` | Chunked text (links to ChromaDB) |
| `compliance_kb` | Curated compliance knowledge base |
| `risk_flags` | AI-detected risky clauses in documents |
| `chat_history` | Full conversation log with AI |

```sql
-- Aise run karo:
psql -U <username> -d <database_name> -f db_schema.sql
```

---

## 🔄 Poora RAG Pipeline — Ek Nazar Mein

```
📄 14 PDFs (templates + compliance + sample contracts)
    │
    ▼  [week2_text_extraction.py]
📝 14 .txt files + all_documents.json
    │
    ▼  [chunking.py]
🔪 242 overlapping text chunks → all_chunks.json
    │
    ▼  [embed_and_store.py]
🔢 242 embedding vectors → ChromaDB (data/vector_db/)
    │
    ▼  [query_test.py — TESTING ONLY]
🔍 User query → embed → top-5 similar chunks retrieved ✅
    │
    ▼  [NEXT: rag_pipeline.py — Week 4]
🤖 Retrieved chunks + Gemini API → Grounded answer generated
```

---

## 📦 Dependencies Installed

```
langchain-text-splitters  → Document chunking
sentence-transformers     → all-MiniLM-L6-v2 embedding model
chromadb                  → Local vector database
psycopg2-binary           → PostgreSQL connection
torch                     → Required by sentence-transformers
fastapi + uvicorn         → Backend API (Week 4+)
python-dotenv             → Environment variables / API keys
pymupdf                   → PDF text extraction
```

Install command:
```bash
uv pip install -r requirements.txt --python "C:\Users\karti\AppData\Local\Programs\Python\Python312\python.exe"
```

---

## ▶️ Scripts Run Karne Ka Order

```bash
# Step 1 — PDF se text nikalo
python week2_text_extraction.py

# Step 2 — Text ko chunks mein todo
python chunking.py

# Step 3 — Chunks ko embed karo aur ChromaDB mein store karo
python embed_and_store.py

# Step 4 — Retrieval test karo
python query_test.py
python query_test.py --category compliance_docs   # sirf compliance search
python query_test.py --category templates         # sirf templates search

# Step 5 — PostgreSQL schema deploy karo (jab DB ready ho)
psql -U postgres -d legal_assistant -f db_schema.sql
```

---

## 🚀 Aage Kya Karna Hai — Week 4 Plan

| Task | Description |
|---|---|
| `rag_pipeline.py` | Gemini API se generation add karo — RAG poora hoga |
| FastAPI backend | `/query`, `/upload`, `/review` endpoints banao |
| PostgreSQL setup | `db_schema.sql` run karo, psycopg2 se connect karo |
| Risk detection | Risky clauses automatically flag karo |
| React frontend | Simple UI — document upload + chat interface |

---

## 💡 Important Concepts — Interview/Viva Ke Liye

| Term | Simple Definition |
|---|---|
| **RAG** | Pehle dhundo (Retrieve), phir AI se jawab banao (Generate) |
| **Chunk** | Document ka ek chhota piece (~700 characters) |
| **Overlap** | Consecutive chunks ke beech common text — context nahi toota |
| **Embedding** | Text → numbers (vectors) — machine samajh sake |
| **Vector DB** | Special database jo vectors store karta hai (ChromaDB) |
| **Semantic Search** | Exact words nahi, meaning se dhundna |
| **Similarity Score** | 0 to 1 — 1 matlab perfect match |
| **all-MiniLM-L6-v2** | Hugging Face ka fast embedding model (384 dimensions) |
| **ChromaDB** | Local vector database — koi cloud/cost nahi |
| **LangChain** | LLM tools ko connect karne ka framework |

---

*Last updated: August 2026 | Week 3 Complete ✅*
