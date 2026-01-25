# EduSphere AI Core - Backend Service

The Core Backend for EduSphere AI, a comprehensive service designed to handle heavy AI processing tasks including document extraction, chunking, summarization, and generation. Built with FastAPI and Python.

## 🏗️ Architecture & Features

This service acts as the intelligence engine for the platform, providing:

- **Authentication:** Secure user management via Firebase and JWT.
- **RAG Pipeline (Retrieval-Augmented Generation):**
  - **Extraction:** extract text and structure from PDFs/Docs using `pdfplumber` and `pdf2docx`.
  - **Chunking:** Semantic segmentation of content for better context retention.
  - **Embedding & Storage:** (Planned/implied via dependencies) using Vector datastores.
  - **Generation:** Content generation using LLMs (local/remote via `ollama`).
  - **Summarization:** Automated improvements of educational texts.
- **Database:** PostgreSQL (via SQLAlchemy & AsyncPG) and support for Firestore/Supabase.
- **Async Processing:** Efficient handling of long-running AI tasks.

## 🛠️ Technology Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Database:** PostgreSQL, Supabase, Firestore, MongoDB (Motor)
- **AI/ML:**
  - `ollama`, `transformers` for LLM interaction
  - `gliner` for Named Entity Recognition (NER)
  - `nltk`, `scikit-learn` for NLP tasks
- **Document Processing:** `pdfplumber`, `pymupdf`, `python-docx`
- **Package Management:** [uv](https://github.com/astral-sh/uv) (for fast Python package management)

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- `uv` (recommended) or `pip`
- PostgreSQL

### Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd edusphere-ai-core
   ```

2. **Install Dependencies:**
   We strictly recommend using `uv` for dependency management.

   ```bash
   uv sync
   ```

   _Alternatively with pip:_

   ```bash
   pip install -e .
   ```

3. **Database Setup:**
   Ensure you have a PostgreSQL instance running.

   ```sql
   CREATE DATABASE edusphere;
   ```

4. **Configuration:**
   Copy `.env.example` (or create a new `.env` file) and configure the following:

   ```bash
   # Database
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/edusphere

   # Security
   SECRET_KEY=your_secret_key_here  # Generate with: openssl rand -hex 32

   # Firebase
   FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

   # External Services (if used)
   SUPABASE_URL=...
   SUPABASE_KEY=...
   ```

5. **Initialize Database:**
   Run the initialization scripts to set up schemas.
   ```bash
   python init_scripts/init_db.py
   ```

### Running the Application

Start the development server using `uv`:

```bash
uv run uvicorn main:app --reload
```

The API docs will be available at `http://localhost:8000/docs`.

## 📂 Project Structure

```
edusphere-ai-core/
├── data/               # Local storage for uploads/images
├── docs/               # Detailed documentation files
├── features/           # Core AI Logic Modules
│   ├── chunking.py     # Text segmentation logic
│   ├── extraction.py   # PDF/Docx text extraction
│   ├── generation.py   # LLM generation pipelines
│   └── summarization.py # Content summarization
├── init_scripts/       # DB & Environment setup scripts
├── models/             # Pydantic & SQLAlchemy Models
├── services/           # Business logic services (Auth, Websocket)
├── utils/              # Helper functions & logging
├── config.py           # Application configuration
└── main.py             # Entry point
```

## 🧪 Testing

You can use the `.http` files in `tests/` for quick API testing using VS Code REST Client extensions, or run Python tests if configured.

```bash
# Example manual run
python manual_run.py
```
