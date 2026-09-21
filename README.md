# AI-Based Legal Document Assistant for Small Businesses

> **An intelligent, full-stack AI assistant tailored for Indian MSMEs, startups, and small businesses to analyze, summarize, risk-check, and query complex legal documents.**

---

## 📌 Project Overview

Small business owners frequently navigate complex legal documents (NDAs, vendor contracts, employment agreements, rental deeds, GST & MSME compliance) without affordable in-house legal counsel. 

This project delivers an end-to-end, production-ready solution featuring:
- **Multi-Format Text Ingestion**: Native extraction from PDFs (PyMuPDF), Word documents (python-docx), and scanned files (Tesseract OCR).
- **Domain-Specific RAG Engine**: Semantic vector search with ChromaDB and `all-MiniLM-L6-v2` embeddings, powered by Google Gemini for grounded Q&A.
- **Contract Risk Analysis**: Automated detection of unfair indemnity, unilateral termination, missing mandatory clauses, and liability exposures.
- **Audio Walkthrough (TTS)**: Text-to-speech voice summaries using gTTS for quick, accessible contract overviews on the go.
- **Full-Stack Architecture**: Modern React (Vite) interface paired with a secure FastAPI backend and PostgreSQL database.

---

## 🏛 System Architecture & Workflow

```text
[ User / Web UI ]
       │
       ▼  (FastAPI REST Endpoints with JWT Auth)
┌─────────────────────────────────────────────────────────────┐
│                       BACKEND API                           │
│  ├── /auth        : User Registration & JWT Authentication  │
│  ├── /documents   : Upload, Text Ingest, AI Risk Analysis  │
│  └── /query       : Context-Grounded Legal RAG & Q&A        │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
       (Document Pipeline)             (RAG Query Engine)
               │                               │
               ▼                               ▼
┌──────────────────────────────┐ ┌─────────────────────────────┐
│     DOCUMENT PROCESSING      │ │      RETRIEVAL (RAG)        │
│  • PyMuPDF / python-docx     │ │  • ChromaDB Vector Store    │
│  • LangChain Chunking        │ │  • all-MiniLM-L6-v2 (384-d) │
│  • Google Gemini 1.5/2.0     │ │  • Indian Law / KB Context  │
│  • gTTS Audio Generation     │ │  • Grounded Source Citations│
└──────────────┬───────────────┘ └─────────────┬───────────────┘
               │                               │
               └───────────────┬───────────────┘
                               ▼
               ┌───────────────────────────────┐
               │    PERSISTENCE & STORAGE      │
               │  • PostgreSQL (Users/Docs)    │
               │  • ChromaDB (Embeddings)      │
               │  • Local Uploads & Audio Cache│
               └───────────────────────────────┘
```

---

## 📂 Project Directory Structure

```text
AI_Bassed_Legal_Doc_Major_Project/
├── .env.example                        # Template environment variables
├── .gitignore                          # Clean repository ignore configuration
├── README.md                           # Project documentation & setup guide
├── PROJECT_DETAILS.md                  # Comprehensive technical report & viva guide
├── requirements.txt                    # Python dependencies
│
├── db_schema.sql                       # PostgreSQL DDL schema (6 tables)
├── migration_add_analysis_cache.sql    # Database migration for analysis caching
│
├── document_ingest.py                  # Text extraction pipeline (PDF, DOCX, OCR)
├── chunking.py                         # Document chunking (RecursiveCharacterTextSplitter)
├── embed_and_store.py                  # Embedding generation & ChromaDB storage
├── rag_pipeline.py                     # Retrieval-Augmented Generation & Gemini integration
├── document_processor.py               # AI contract analysis (Summary, Clauses, Risks, TTS)
├── query_test.py                       # CLI tool for testing retrieval quality
│
├── backend/                            # FastAPI REST API
│   ├── auth.py                         # JWT token creation & password hashing
│   ├── database.py                     # SQLAlchemy database engine & session maker
│   ├── dependencies.py                 # FastAPI auth & DB dependency injection
│   ├── main.py                         # FastAPI entry point & CORS configuration
│   ├── models.py                       # SQLAlchemy 2.0 ORM models
│   ├── schemas.py                      # Pydantic v2 validation schemas
│   └── routers/                        # API route handlers
│       ├── auth_routes.py              # User authentication routes
│       ├── documents_routes.py         # Document upload, analysis, audio & Q&A
│       └── query_routes.py             # General legal knowledge-base query route
│
├── frontend/                           # React + Vite Web Client
│   ├── src/
│   │   ├── components/                 # UI components (Navbar, Sidebar, Upload, etc.)
│   │   ├── context/                    # AuthContext & state providers
│   │   ├── pages/                      # Dashboard, Workspace, Query, Login, Register
│   │   ├── styles/                     # Modern dark-mode aesthetic CSS
│   │   ├── api.js                      # Axios client with JWT interceptors
│   │   ├── App.jsx                     # Root application routing
│   │   └── main.jsx                    # Application mount point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── data/                               # Knowledge Base & Evaluation Datasets
│   ├── templates/                      # Standard business contract PDFs
│   ├── compliance_docs/                # Indian compliance PDFs (GST, MSME, Labour, etc.)
│   ├── sample_contracts/               # Test contract samples with risky clauses
│   ├── reference/                      # Risk clause reference checklist
│   ├── extracted_text/                 # Extracted text & all_documents.json
│   ├── chunks/                         # Chunked data — all_chunks.json
│   └── vector_db/                      # ChromaDB persistent vector database
│
├── uploads/                            # Runtime uploaded files (.gitkeep)
└── audio_cache/                        # Runtime TTS generated audio files (.gitkeep)
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python**: 3.10+ (Recommended: 3.11 or 3.12)
- **Node.js**: 18+ and npm
- **PostgreSQL**: 14+ running locally or remotely
- **Google Gemini API Key**: Obtain from [Google AI Studio](https://aistudio.google.com/)

---

### 2. Environment Configuration
Copy `.env.example` to `.env` in the root folder and configure your credentials:

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/legal_assistant

# AI & APIs
GEMINI_API_KEY=your_gemini_api_key_here

# Security
JWT_SECRET_KEY=your_strong_random_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

---

### 3. Database Initialization
Create your PostgreSQL database and run the schema setup:

```bash
# Create database (via psql or pgAdmin)
psql -U postgres -c "CREATE DATABASE legal_assistant;"

# Apply initial schema
psql -U postgres -d legal_assistant -f db_schema.sql

# Apply analysis cache migration
psql -U postgres -d legal_assistant -f migration_add_analysis_cache.sql
```

---

### 4. Backend Setup
Set up the Python virtual environment and launch the FastAPI server:

```bash
# 1. Activate your virtual environment
venv\Scripts\activate       # On Windows
# or source venv/bin/activate # On Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start FastAPI server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

### 5. Frontend Setup
Launch the React development server:

```bash
cd frontend
npm install
npm run dev
```

- **Application URL**: [http://localhost:5173](http://localhost:5173)

---

### 6. (Optional) Rebuilding the Knowledge Base
To re-extract and re-index the standard legal documents into ChromaDB:

```bash
# Step 1: Extract text from PDFs
python document_ingest.py

# Step 2: Split text into overlapping semantic chunks
python chunking.py

# Step 3: Embed and index into ChromaDB
python embed_and_store.py

# Step 4: Test retrieval via CLI
python query_test.py
```

---

## 📑 Core API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new small business user account |
| `POST` | `/auth/login` | Authenticate and obtain JWT access token |
| `GET` | `/documents` | List all documents uploaded by authenticated user |
| `POST` | `/documents/upload` | Upload PDF, DOCX, or image document for processing |
| `POST` | `/documents/{id}/analyze` | Trigger AI summarization, clause extraction & risk analysis |
| `GET` | `/documents/{id}/audio` | Stream/download gTTS synthesized audio overview |
| `POST` | `/documents/{id}/query` | Ask questions grounded specifically in the uploaded document |
| `POST` | `/query` | Ask natural language questions against the general legal knowledge base |
| `GET` | `/health` | API health check status |

---

## ⚖️ Legal Disclaimer
This software is an AI-powered assistant designed for informational and educational purposes only. It does **not** constitute legal advice, nor does it create an attorney-client relationship. Users should always consult a licensed legal professional before executing legally binding agreements.

---

## 📜 License
This project is licensed under the MIT License.
