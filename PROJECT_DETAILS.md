# AI-Based Legal Document Assistant for Small Businesses
### Comprehensive Project Documentation
> **Purpose:** This document covers all aspects of the project — from problem statement to tech stack, timeline, workflow, and future scope — to help in preparing PPT slides and a synopsis/project report.

---

## 📌 Table of Contents
1. [Problem Statement](#1-problem-statement)
2. [Project Overview](#2-project-overview)
3. [Objectives](#3-objectives)
4. [Key Features](#4-key-features)
5. [Data and Resources](#5-data-and-resources)
6. [System Architecture & Workflow](#6-system-architecture--workflow)
7. [Solving Technique — RAG Pipeline](#7-solving-technique--rag-pipeline)
8. [Tech Stack](#8-tech-stack)
9. [Database Design](#9-database-design)
10. [Project Timeline (Week-by-Week)](#10-project-timeline-week-by-week)
11. [Current Progress](#11-current-progress)
12. [Results and Impact](#12-results-and-impact)
13. [Outcome](#13-outcome)
14. [Future Scope (Upcoming Work)](#14-future-scope-upcoming-work)
15. [Challenges and Solutions](#15-challenges-and-solutions)

---

## 1. Problem Statement

Small businesses in India — especially startups, MSMEs, freelancers, and shop owners — deal with a large number of legal documents every day: business contracts, NDAs, GST compliance notices, rent agreements, employment contracts, and more. However:

- **Legal experts are expensive** — hiring a lawyer for every contract review is not affordable for small businesses.
- **Legal language is complex** — legal documents are written in difficult English that most business owners cannot easily understand.
- **Compliance is confusing** — Indian laws like GST, MSME Act, Shops & Establishments Act, and Labour Laws change frequently, and keeping up is difficult.
- **There is no affordable, intelligent tool** available that can help small businesses understand their legal documents, detect risky clauses, and answer compliance-related questions instantly.

### Core Problem:
> *"How can we make legal document understanding accessible, fast, and affordable for small business owners in India who lack legal expertise?"*

---

## 2. Project Overview

**Project Name:** AI-Based Legal Document Assistant for Small Businesses

**Type:** Major Project (AI + NLP + Backend + Frontend)

**Domain:** Legal Tech / Artificial Intelligence / Natural Language Processing

**Target Users:** Small business owners, MSME entrepreneurs, freelancers, startups in India

**Goal:** Build an intelligent AI-powered assistant that can:
- Read and understand PDF legal documents
- Answer natural language questions about those documents
- Detect risky or unfair clauses in contracts
- Provide compliance guidance based on Indian laws (GST, MSME, Labour Law, etc.)
- Summarize complex legal language into simple, plain English

---

## 3. Objectives

1. **Automate Legal Document Reading** — Extract and process text from PDF legal documents automatically.
2. **Enable Smart Q&A** — Allow users to ask questions about their documents in plain English and get clear, source-cited answers.
3. **Detect Contract Risks** — Automatically identify risky, missing, or unfair clauses in uploaded contracts.
4. **Provide Compliance Guidance** — Help users understand GST, MSME, Labour Laws, and other Indian regulations.
5. **Build a Full-Stack Product** — Create a complete web application with a user-friendly frontend and a robust FastAPI backend.
6. **Ensure Accuracy and Safety** — Always cite sources and append a legal disclaimer to prevent misuse of AI-generated information.

---

## 4. Key Features

### Implemented Features
| Feature | Description |
|---|---|
| **PDF Text Extraction** | Extracts text from PDFs using PyMuPDF (fitz), preserving page structure |
| **Document Chunking** | Splits large documents into overlapping chunks (700 chars, 100-char overlap) using LangChain |
| **Vector Embedding** | Converts text chunks into 384-dimension semantic vectors using all-MiniLM-L6-v2 |
| **Vector Database** | Stores all embeddings in ChromaDB with cosine similarity indexing for fast retrieval |
| **Category Filtering** | Supports filtering searches by document category (templates, compliance_docs, sample_contracts) |
| **RAG Pipeline** | Complete Retrieval-Augmented Generation pipeline — query → embed → retrieve → prompt → generate |
| **AI Q&A with Citations** | Uses Google Gemini API to generate answers, always citing source documents |
| **Legal Disclaimer** | Automatically appends a legal disclaimer to every AI-generated response |
| **CLI Interface** | Interactive command-line interface for testing and querying |
| **PostgreSQL Schema** | Full relational database schema designed for the backend API |

### Planned / In Progress
| Feature | Description |
|---|---|
| **FastAPI Backend** | REST API endpoints for document upload, querying, and user management |
| **User Authentication** | JWT-based login/register for small business users |
| **Contract Risk Detection** | AI pipeline to auto-detect risky clauses (high/medium/low/critical severity) |
| **Web Frontend** | React or HTML/CSS based user interface for document upload and chat |
| **Document Summarization** | Auto-summarize any uploaded legal document in plain English |
| **Chat History** | Persistent conversation history stored in PostgreSQL |
| **File Upload API** | Endpoint to upload PDFs and trigger the processing pipeline automatically |

---

## 5. Data and Resources

### Document Categories (Knowledge Base)

The system works with three categories of legal documents:

| Category | Description | Examples |
|---|---|---|
| templates/ | Standard legal document templates | NDA templates, Service Agreement templates, Employment Contract templates |
| compliance_docs/ | Indian compliance regulations | GST registration guide, MSME Act summary, Labour Law FAQs, Startup India docs |
| sample_contracts/ | Real-world sample contracts | Rental agreements, vendor contracts, freelancer agreements |

### Data Storage Structure
```
data/
├── templates/          → Standard legal document PDFs
├── compliance_docs/    → Indian law & regulation PDFs
├── sample_contracts/   → Sample business contracts
├── extracted_text/     → Extracted plain text from PDFs (all_documents.json)
├── chunks/             → Chunked documents (all_chunks.json) — 242+ chunks
├── vector_db/          → ChromaDB persistent vector database (384-dim embeddings)
└── reference/          → Reference materials
```

### AI Models Used
| Model | Purpose | Dimensions |
|---|---|---|
| all-MiniLM-L6-v2 (SentenceTransformers) | Text embedding for semantic search | 384-dim vectors |
| gemini-3.6-flash (Google Gemini API) | Answer generation from retrieved context | — |

### External APIs
- **Google Gemini API** — Powers the language model generation step (free tier available via Google AI Studio)

---

## 6. System Architecture & Workflow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Web Browser)                        │
│              Uploads PDF / Asks a Legal Question                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Web UI)                            │
│          HTML/CSS/JS or React — Document Upload + Chat UI        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACKEND (FastAPI — Python)                       │
│  /upload   /query   /summarize   /risk-check   /auth             │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌─────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│ PDF         │    │ RAG PIPELINE        │    │ PostgreSQL DB    │
│ Extraction  │    │ 1. Embed Query      │    │ users            │
│ (PyMuPDF)   │    │ 2. ChromaDB Search  │    │ documents        │
└──────┬──────┘    │ 3. Build Prompt     │    │ document_chunks  │
       │           │ 4. Call Gemini API  │    │ chat_history     │
       ▼           │ 5. Return Answer    │    │ compliance_kb    │
┌─────────────┐    └──────────┬──────────┘    │ risk_flags       │
│ Chunking    │               │               └──────────────────┘
│ (LangChain) │               ▼
└──────┬──────┘    ┌─────────────────────┐
       │           │  Google Gemini API  │
       ▼           │  (LLM Generation)   │
┌─────────────┐    └─────────────────────┘
│ Embedding   │
│ (MiniLM)   │
│ ChromaDB   │
└─────────────┘
```

### Complete Data Flow (Step-by-Step)

**Step 1: Document Ingestion (Week 2)**
1. PDFs are placed in data/templates/, data/compliance_docs/, or data/sample_contracts/
2. week2_text_extraction.py reads each PDF using PyMuPDF
3. Text is extracted page-by-page with page markers ([PAGE 1], [PAGE 2], etc.)
4. Cleaned text is saved to data/extracted_text/all_documents.json

**Step 2: Chunking (Week 3)**
1. chunking.py loads all_documents.json
2. LangChain's RecursiveCharacterTextSplitter splits each document into overlapping chunks
3. Settings: chunk size = 700 characters, overlap = 100 characters
4. Split priority: paragraphs → sentences → words
5. Each chunk gets metadata: chunk_id, filename, category, chunk_index
6. Result: 242+ chunks saved to data/chunks/all_chunks.json

**Step 3: Embedding & Vector Storage (Week 3)**
1. embed_and_store.py loads all chunks
2. all-MiniLM-L6-v2 model converts each chunk into a 384-dimensional vector
3. Vectors + metadata are stored in ChromaDB (data/vector_db/) using cosine similarity (HNSW index)
4. Process is idempotent — re-running safely upserts existing vectors

**Step 4: Query & Answer — RAG Pipeline (Week 4)**
1. User types a natural language question
2. Question is embedded using the same MiniLM model
3. ChromaDB returns top-7 most semantically similar chunks (with similarity scores)
4. A structured prompt is built including system instructions + context + user question
5. Gemini API generates a grounded answer with citations
6. Response includes: answer text + source documents + similarity scores + legal disclaimer

---

## 7. Solving Technique — RAG Pipeline

### What is RAG?
**RAG (Retrieval-Augmented Generation)** is a technique that combines:
- **Retrieval** — Finding the most relevant information from a knowledge base
- **Augmented Generation** — Using that retrieved information to generate a factual, grounded answer

### Why RAG instead of fine-tuning?
| Aspect | Fine-Tuning | RAG (Our Approach) |
|---|---|---|
| Cost | Very expensive (GPU hours) | Free / low-cost |
| Updatable | Requires retraining | Just add new documents |
| Source Citations | Not possible | Built-in |
| Hallucinations | High risk | Greatly reduced |
| Legal Accuracy | Cannot guarantee | Grounded in actual docs |

### How Our RAG Works

```
User Question
     │
     ▼
[Embed Query] ─── all-MiniLM-L6-v2 ──→ 384-dim vector
     │
     ▼
[ChromaDB Search] ─── cosine similarity ──→ Top-7 chunks
     │
     ▼
[Build Prompt]
     ├── System Instruction (strict rules for AI)
     ├── Context Sections (7 retrieved chunks with source labels)
     ├── Output Instructions (cite sources + add disclaimer)
     └── User Question
     │
     ▼
[Gemini API] ─── temperature=0.2 ──→ Grounded, cited answer
     │
     ▼
[Structured Response]
     ├── answer (text)
     ├── sources (list of filenames + similarity scores)
     ├── chunks_used (count)
     └── model (name)
```

### Key Design Decisions
- **Temperature = 0.2** — Low temperature for factual, consistent answers (not creative)
- **Top-K = 7** — Higher retrieval depth gives richer context to the LLM
- **Strict Prompt Rules** — AI is instructed to ONLY use provided context (no hallucinations)
- **Model Fallback** — If primary Gemini model is unavailable, system automatically tries fallback models
- **Rate Limit Handling** — Automatic retry with exponential backoff on 429 errors
- **Cosine Similarity** — Converts ChromaDB distance [0,2] to similarity [0,1] for user-friendly display

---

## 8. Tech Stack

### Core AI / ML
| Technology | Version/Model | Purpose |
|---|---|---|
| Google Gemini API | gemini-3.6-flash | Large Language Model for answer generation |
| SentenceTransformers | all-MiniLM-L6-v2 | Text embedding (384-dimensional vectors) |
| ChromaDB | Latest | Local persistent vector database |
| LangChain | langchain-text-splitters | Document chunking with RecursiveCharacterTextSplitter |

### Backend
| Technology | Purpose |
|---|---|
| Python 3.11+ | Core programming language |
| FastAPI | REST API framework (planned for next phase) |
| Uvicorn | ASGI server for FastAPI |
| PostgreSQL | Relational database for users, documents, chat history |
| psycopg2-binary | PostgreSQL adapter for Python |

### PDF Processing
| Technology | Purpose |
|---|---|
| PyMuPDF (fitz) | Primary PDF text extraction (fast, accurate) |
| pytesseract | OCR for scanned/image PDFs (fallback) |
| Pillow | Image processing support for OCR |

### Frontend (Planned)
| Technology | Purpose |
|---|---|
| HTML / CSS / JavaScript | Core web technologies |
| React / Vite | Interactive UI framework |

### Utilities
| Technology | Purpose |
|---|---|
| python-dotenv | Secure API key management via .env file |
| argparse | CLI argument parsing |
| json | Data serialization between pipeline stages |
| pathlib | Cross-platform file path management |

### Development Environment
| Tool | Details |
|---|---|
| OS | Windows |
| IDE | VS Code with AI Assistant |
| Version Control | Git / GitHub |
| Virtual Environment | Python venv |
| API Key Source | Google AI Studio (aistudio.google.com) |

---

## 9. Database Design

The PostgreSQL database has 6 tables covering the complete application:

### Tables Overview

| Table | Purpose |
|---|---|
| users | Registered small business users (UUID PK, email, bcrypt password hash, business name) |
| documents | Tracks uploaded legal documents per user (status: pending → processing → ready → error) |
| document_chunks | Stores chunked text with links to ChromaDB embedding IDs |
| compliance_kb | Curated Indian compliance knowledge base (GST, MSME, Labour Law topics) |
| risk_flags | AI-detected risky clauses per document (severity: low/medium/high/critical) |
| chat_history | Complete conversation log (user_id, document_id, query, AI response, timestamp) |

### Entity Relationship Summary
```
users (1) ──── (N) documents (1) ──── (N) document_chunks
  │                    │
  │                    └──── (N) risk_flags
  │
  └──── (N) chat_history ────── (optional) documents
```

---

## 10. Project Timeline (Week-by-Week)

| Week | Phase | Tasks | Status |
|---|---|---|---|
| Week 1 | Project Setup | Project structure, Git init, requirements.txt, .env config, data folder organization | Done |
| Week 2 | PDF Text Extraction | PyMuPDF integration, text extraction from 3 categories, page-by-page extraction, cleaning, JSON output | Done |
| Week 3 | Chunking + Embedding + Vector DB | LangChain chunking (700-char, 100 overlap), MiniLM embedding, ChromaDB storage, retrieval testing, PostgreSQL schema | Done |
| Week 4 | RAG Generation Pipeline | Full RAG pipeline, Gemini API, prompt engineering, source citation, legal disclaimer, model fallback, CLI | Done |
| Week 5 | FastAPI Backend | REST API: /upload, /query, /summarize, /risk-check, JWT auth endpoints | Upcoming |
| Week 6 | Risk Detection | AI clause detection, populate risk_flags table, severity classification | Upcoming |
| Week 7 | Frontend Development | Web UI for document upload, chat interface, risk report dashboard | Upcoming |
| Week 8 | Integration & Testing | End-to-end testing, bug fixes, performance tuning, deployment preparation | Upcoming |

---

## 11. Current Progress

### Completed (Weeks 1–4)

**Pipeline Status:**
```
[DONE] Week 2: PDF Extraction     →  PDFs → cleaned text → all_documents.json
[DONE] Week 3: Chunking           →  text → 242+ overlapping chunks (all_chunks.json)
[DONE] Week 3: Embedding          →  chunks → 384-dim vectors → ChromaDB
[DONE] Week 3: Retrieval Testing  →  CLI test of vector similarity search
[DONE] Week 3: DB Schema          →  6-table PostgreSQL schema designed
[DONE] Week 4: RAG Pipeline       →  Full query → retrieve → generate → answer pipeline
```

**What the System Can Do Right Now:**
- Accept a natural language question via CLI
- Embed the question using the MiniLM model
- Retrieve top 7 most relevant legal document chunks from ChromaDB
- Build a structured prompt with strict grounding rules
- Call Google Gemini API and get a factual, cited answer
- Display the answer with source citations and similarity scores
- Handle API errors, rate limits, and model fallbacks gracefully
- Filter searches by document category

### In Progress / Upcoming
- FastAPI backend endpoints
- User authentication system
- Web-based frontend
- Risk clause detection module
- Document summarization feature
- Chat history persistence

---

## 12. Results and Impact

### Technical Results

| Metric | Value |
|---|---|
| Documents Processed | Multiple PDFs across 3 categories |
| Total Chunks Created | 242+ overlapping chunks |
| Embedding Dimensions | 384-dimensional vectors (all-MiniLM-L6-v2) |
| Default Retrieval Depth | Top-7 most relevant chunks per query |
| LLM Response Temperature | 0.2 (controlled, factual answers) |
| Similarity Scoring | Cosine similarity [0.0 to 1.0] |
| Model Fallback Chain | 4 Gemini model variants supported |
| Rate Limit Handling | Automatic retry with 15s × attempt backoff |

### Business Impact

1. **Cost Reduction for Small Businesses** — Eliminates the need to hire a lawyer for every basic legal query. A small business owner can get instant, source-backed answers about their contracts.

2. **Democratization of Legal Knowledge** — Makes legal information accessible to people who cannot afford legal counsel, especially in Tier-2 and Tier-3 cities across India.

3. **Faster Decision Making** — Instead of reading 30+ pages of a contract, users can ask: "Does this contract have a non-compete clause?" and get an instant answer.

4. **Compliance Awareness** — Helps businesses understand GST, MSME, Labour Law, and Startup India requirements without confusion.

5. **Risk Prevention** — By detecting risky or missing clauses before signing, businesses can avoid costly legal disputes.

6. **Scalable Knowledge Base** — New legal documents or regulation updates can be added simply by placing PDFs in the data folder and re-running the pipeline — no retraining required.

---

## 13. Outcome

### What the Final Product Will Deliver

By the end of the project, the AI-Based Legal Document Assistant will be a complete, deployable web application providing:

1. **A Smart Q&A Chatbot** — Ask anything about a legal document, get a grounded answer with source citations.

2. **Contract Risk Analyzer** — Upload any contract and receive a risk report highlighting dangerous, missing, or unfair clauses with severity ratings (Low / Medium / High / Critical).

3. **Compliance Navigator** — Ask about GST registration, MSME benefits, labour laws, and more — and get clear, regulation-backed answers.

4. **Document Summarizer** — Get a plain-English summary of any uploaded legal document in seconds.

5. **Persistent Chat Sessions** — Users can log in, manage their documents, and review past conversations.

6. **Full REST API** — A well-documented FastAPI backend that can be integrated with any frontend or mobile app.

### Expected Value for Target Users
- Small business owners save hours of reading and thousands of rupees in lawyer fees for routine document review.
- The system never gives a confident wrong answer — it always says it doesn't know if the document doesn't contain the answer.
- Every response comes with source citations so users can verify the information themselves.

---

## 14. Future Scope (Upcoming Work)

### Short-Term (Next 4 Weeks — Weeks 5–8)

**Week 5 — FastAPI Backend:**
- POST /auth/register — User registration
- POST /auth/login — JWT authentication
- POST /documents/upload — PDF upload + auto-processing
- POST /query — RAG-powered Q&A endpoint
- GET /documents/{id}/risk — Risk analysis report
- GET /documents/{id}/summary — Document summary

**Week 6 — Risk Detection AI Pipeline:**
- Detect missing clauses (e.g., no dispute resolution clause)
- Identify unfair or one-sided terms
- Classify severity (low/medium/high/critical)
- Store results in risk_flags PostgreSQL table

**Week 7 — Web Frontend:**
- Clean, modern UI for document upload
- Chat-style interface for Q&A
- Risk report dashboard with color-coded flags
- User authentication screens

**Week 8 — Integration & Testing:**
- End-to-end pipeline testing with real documents
- API testing with Postman/pytest
- Performance optimization

### Medium-Term (Future Enhancements)

- **Multi-Language Support** — Translate legal explanations into Hindi and regional languages
- **Email Alerts** — Notify users when contracts contain high-risk clauses
- **Clause Comparison** — Compare two versions of a contract side-by-side
- **Legal Templates Generator** — Generate standard contracts from user inputs
- **Mobile App** — React Native mobile application
- **Cloud Deployment** — Deploy on AWS/GCP/Azure with Docker containers

---

## 15. Challenges and Solutions

| Challenge | Solution Applied |
|---|---|
| Gemini API Model Deprecation | Implemented a 4-model fallback chain: if primary model unavailable (404/503), automatically try next model |
| Rate Limits on Free Tier | Auto-retry with exponential backoff (15s × attempt), user-friendly error messages |
| Unicode/Emoji on Windows Terminal | Force UTF-8 encoding (sys.stdout.reconfigure) at top of every script |
| Large PDF Files | Chunk-based processing (700-char chunks) keeps memory usage low regardless of document size |
| AI Hallucinations | Strict prompt rules: Answer ONLY using provided context; if not in context, say you don't know |
| Re-running Scripts Safely | ChromaDB upsert (not add) — idempotent, safe to re-run without duplicating data |
| Context Quality | Top-K increased to 7 for richer context; similarity scores shown so users can judge relevance |
| Legal Liability | Mandatory legal disclaimer appended to every AI response |

---

## Project File Structure

```
AI_Bassed_Legal_Doc_Major_Project/
│
├── week2_text_extraction.py  → Week 2: PDF text extraction using PyMuPDF
├── chunking.py               → Week 3: LangChain document chunking
├── embed_and_store.py        → Week 3: Embedding + ChromaDB storage
├── query_test.py             → Week 3: Retrieval testing CLI (no LLM)
├── rag_pipeline.py           → Week 4: Full RAG pipeline (main module)
├── db_schema.sql             → PostgreSQL 6-table schema
├── check_models.py           → Utility: Check available Gemini models
├── requirements.txt          → All Python dependencies
├── .env                      → API keys (GEMINI_API_KEY)
│
├── data/
│   ├── templates/            → Standard legal document PDFs
│   ├── compliance_docs/      → Indian law & regulation PDFs
│   ├── sample_contracts/     → Sample business contract PDFs
│   ├── extracted_text/       → Extracted text + all_documents.json
│   ├── chunks/               → Chunked data — all_chunks.json
│   └── vector_db/            → ChromaDB persistent vector database
│
├── backend/                  → FastAPI backend (Week 5)
├── frontend/                 → Web UI (Week 7)
├── notebooks/                → Jupyter notebooks for experimentation
└── docs/                     → Additional project documentation
```

---

## Key Takeaways for PPT / Report

1. **Problem is Real and Large** — Millions of small businesses in India need legal help but cannot afford it.
2. **RAG is the Right Approach** — It provides grounded, citation-backed answers without expensive GPU fine-tuning.
3. **Architecture is Production-Ready** — Designed with scalability, error handling, and safety in mind.
4. **Strong 4-Week Progress** — From zero to a fully working AI Q&A pipeline in 4 weeks.
5. **Clear Roadmap** — A detailed plan exists for completing the full web application in 4 more weeks.
6. **Real Impact** — This tool saves small businesses time and money while making legal knowledge accessible to everyone.

---

*Document prepared: August 2026*
*Project: AI-Based Legal Document Assistant for Small Businesses*
*Technology: Python + Google Gemini AI + ChromaDB + FastAPI + PostgreSQL*
