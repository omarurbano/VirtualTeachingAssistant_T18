# Virtual Teaching Assistant (VTA)

A Multimodal AI-Driven Learning Assistant designed for the NVIDIA Deep Learning Institute (DLI) at Washington State University. The system provides grounded, transparent assistance for learners working with instructional notebooks, diagrams, and recorded content.

## Project Overview

The VTA uses a Mixture-of-Experts architecture with specialized AI modules for text, vision-language, and audio processing. It features intelligent query routing, source-grounded retrieval with RAG, and personalized learning support.

## Team Members

- **Omar Urbano-Rendon** - Computer Science student with minor in Mathematics
- **Niranjan Y. Sudinani** - Honors Computer Science student, Technical Lead
- **Don Manuel Jose** - Senior in Computer Science, ML and Data Engineering
- **Duncan Hintz** - Team Member

**Client:** Parteek Kumar (NVIDIA DLI University Ambassador)

## Quick Start

```bash
# Navigate to backend code
cd Code/backend

# Install dependencies
pip install -r requirements.txt

# Start the Flask application
python app.py

# The application will be available at http://localhost:5000
```

## Project Structure

```
VirtualTeachingAssistant_T18/
├── Code/                      # All source code
│   ├── backend/              # Python backend (Flask API, RAG pipeline)
│   │   ├── app.py            # Main Flask application
│   │   ├── requirements.txt  # Python dependencies
│   │   ├── document_loader.py
│   │   ├── embedding_manager.py
│   │   ├── vector_store.py
│   │   ├── multimodal_processor.py
│   │   ├── NemotronNano.py   # Vision model integration
│   │   ├── plans/            # Implementation plans and documentation
│   │   └── ...
│   ├── frontend/             # Web frontend (HTML/CSS/JS)
│   │   ├── templates/        # HTML templates
│   │   └── static/           # CSS and JavaScript
│   ├── instructor_ui/        # Instructor dashboard UI
│   └── docs/                 # Technical documentation
│
├── Data/                     # Project datasets
├── Sprints/                  # Sprint documentation and reports
├── Reports/                  # Project reports (CPTS421, CPTS423)
├── Evaluation/               # Evaluation metrics
├── Testing/                  # Test strategies
├── Deployment/               # Deployment configurations
├── Reflections/              # Team reflections
├── Resources/                # Links and references
├── Rubric/                   # Grading rubrics
└── README.md
```

## Technical Stack

- **Framework:** Flask, NVIDIA NeMo, LangChain
- **Models:** 
  - all-MiniLM-L6-v2 (embeddings)
  - Gemini 1.5 Flash (cloud inference)
  - Nemotron (vision-language)
- **Document Processing:** Unstructured library, YOLOX, Table-Transformer
- **Database:** PostgreSQL (via node.js server)

## Features

- **Multi-format Document Support**: PDF, Word (.docx), Text (.txt), Audio (MP3, WAV, OGG, M4A, FLAC)
- **Multimodal Processing**: Extracts text, tables, images with OCR from PDFs
- **Vector Search**: Semantic similarity search using sentence-transformers
- **Answer Generation**: Uses local AI models (Ollama/GPT4All) or returns retrieved content
- **Proper Citations**: Every answer includes page numbers and verbatim text from source documents
- **Instructor Dashboard**: Learning insights from aggregated student queries

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/health` | GET | Health check |
| `/api/initialize` | POST | Initialize RAG |
| `/api/upload` | POST | Upload file |
| `/api/query` | POST | Ask question |
| `/api/files` | GET | List files |
| `/api/clear` | POST | Clear all |

## Documentation

More detailed documentation can be found in `Code/docs/`:
- Technical documentation
- Implementation plans
- Project summaries
- Sprint reports

## Requirements

- Python 3.9+
- Node.js (for server components)
- See `Code/backend/requirements.txt` for Python dependencies