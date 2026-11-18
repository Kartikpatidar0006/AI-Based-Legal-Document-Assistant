FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies: Tesseract OCR + graphics & glib libraries (needed by PyMuPDF and Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with UID 1000 (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user

# Configure environment paths for non-root user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface

WORKDIR $HOME/app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Upgrade pip and install Python packages (CPU-only PyTorch and pinned backend libraries)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model at build time as the non-root user so it caches into HF_HOME
USER user
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application source code into container
USER root
COPY --chown=user:user . .

# Ensure data/ (with ChromaDB), uploads/, and audio_cache/ exist and are fully writable by user 1000
RUN mkdir -p data/vector_db uploads audio_cache && \
    chown -R user:user data uploads audio_cache && \
    chmod -R 775 data uploads audio_cache

# Switch back to non-root user for execution
USER user

# Hugging Face Spaces default HTTP port
EXPOSE 7860

# Launch FastAPI backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]

