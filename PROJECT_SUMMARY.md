# TradeBuzz-1 Virtual Teaching Assistant - Comprehensive Project Summary

## Executive Overview

**Project Name:** TradeBuzz-1 VTA (Virtual Teaching Assistant)  
**Course:** CPT_S 421 - Vision Things AI  
**Development Team:** CPT_S 421 Development Team  
**Version:** 1.0.0  
**Deployment Target:** Integration with NVIDIA DLI courses and WSU Canvas LMS

---

## 1. Project Purpose & Vision

The TradeBuzz-1 VTA is a web-based **Retrieval-Augmented Generation (RAG)** system that enables users to upload various document types and ask questions about their content. The system provides accurate answers with proper citations, including page numbers and verbatim text from source documents.

### Primary Objectives
1. **Document Ingestion**: Accept and process multiple file formats with automatic format detection
2. **Content Extraction**: Extract text, tables, and images with OCR capabilities
3. **Semantic Indexing**: Create vector embeddings for efficient similarity search
4. **Question Answering**: Retrieve relevant context and generate accurate answers
5. **Citation Generation**: Provide verifiable citations with precise location information
6. **Honest Responses**: Clearly indicate when information is not found in documents

### Target Integration
- **NVIDIA DLI Courses**: GPU-accelerated AI model processing for coursework
- **WSU Canvas**: LTI (Learning Tools Interoperability) integration for course management

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Terminal-style UI (HTML/CSS/JS)                     │  │
│  │  - File upload (documents & images)                 │  │
│  │  - Chat interface                                   │  │
│  │  - Citation display                                 │  │
│  └───────────────────────┬──────────────────────────────┘  │
└───────────────────────────│──────────────────────────────────┘
                            │ REST API (JSON)
┌───────────────────────────▼──────────────────────────────────┐
│                    Backend (Flask)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Flask Application (app.py)                          │  │
│  │  - Request routing                                   │  │
│  │  - File handling                                     │  │
│  │  - State management                                  │  │
│  └───────────────────────┬──────────────────────────────┘  │
│                          │                                  │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │  RAG Application State (Global)                      │  │
│  │  - Document Processor                                │  │
│  │  - Embedding Manager                                 │  │
│  │  - Vector Store                                      │  │
│  │  - Answer Generator                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ sentence-     │   │ NVIDIA        │   │ OpenAI        │
│ transformers  │   │ Nemotron      │   │ Whisper       │
│ (local)       │   │ (cloud API)   │   │ (optional)    │
└───────────────┘   └───────────────┘   └───────────────┘
```

### Technology Stack
- **Backend:** Python 3.9+, Flask 2.3+, Flask-CORS
- **Frontend:** HTML5, CSS3, Vanilla JavaScript (no frameworks)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- **Document Processing:** LangChain, PyPDF, python-docx, unstructured
- **Vector Store:** In-memory numpy-based with optional ChromaDB
- **Vision AI:** NVIDIA Nemotron-Nano API (cloud-based) or BLIP-2 (local)
- **Audio Transcription:** OpenAI Whisper (optional)
- **OCR:** pytesseract, pdf2image

---

## 3. Core Features

### 3.1 Document Support

| File Type | Extension | Processing Method |
|-----------|-----------|-------------------|
| PDF | .pdf | PyMuPDF (multimodal extraction) |
| Word | .docx | Docx2txtLoader |
| Text | .txt | TextLoader |
| Audio | .mp3, .wav, .ogg, .m4a, .flac | Whisper transcription |
| Images | .png, .jpg, .jpeg, .webp, .gif, .bmp | BLIP-2 + OCR |

### 3.2 Multimodal Processing

The system extracts and processes:
- **Text**: With bounding boxes and semantic boundaries
- **Tables**: Detected via layout analysis, converted to Markdown
- **Images**: Extracted as PNG, analyzed with BLIP-2 for captions, OCR for embedded text
- **Audio**: Transcribed with Whisper, chunked with timestamps

### 3.3 Answer Generation

- **Confidence Levels**: High (≥0.7), Medium (≥0.4), Low (≥0.2), None (<0.2)
- **Answer Types**: found, not_found, partial, ambiguous
- **Citation Limit**: Configurable max citations (default: 10)
- **Similarity Threshold**: Minimum score for relevance (default: 0.3)

---

## 4. Module Breakdown

### 4.1 app.py (Main Application)
- Flask server with REST API endpoints
- Global state management (RAGApplicationState)
- File upload and processing
- Query handling and response generation

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/health` | GET | Health check |
| `/api/initialize` | POST | Initialize RAG |
| `/api/upload` | POST | Upload file |
| `/api/upload/image` | POST | Upload image |
| `/api/query` | POST | Ask question |
| `/api/files` | GET | List files |
| `/api/images` | GET | List images |
| `/api/clear` | POST | Clear all |

### 4.2 embedding_manager.py
- SentenceTransformerEmbeddings for local embeddings
- OpenAIEmbeddingsWrapper for cloud embeddings
- MockEmbeddings for testing
- Multi-provider support with fallback

### 4.3 vector_store.py
- InMemoryVectorStore with cosine similarity search
- DocumentChunk class with rich metadata
- Metadata indexing for fast filtering
- Optional ChromaDB persistence

### 4.4 citation_tracker.py
- CitationSource class for tracking sources
- CitationFormatter with multiple styles (numbered, APA, inline, verbatim)
- CitationTracker for managing citations

### 4.5 answer_generator.py
- AnswerContext for retrieved context
- GeneratedAnswer with full context
- AnswerGenerator with confidence scoring
- Honest "not found" responses

### 4.6 pdf_extractor.py
- PyMuPDFExtractor for multimodal PDF extraction
- PDFPage, TextBlock, PDFImage, PDFTable classes
- Image extraction as PNG bytes
- Table detection via layout analysis

### 4.7 image_analyzer.py
- BLIP-2 vision model integration
- OCR text extraction with pytesseract
- Batch processing support
- Windows Tesseract path configuration

### 4.8 multimodal_chunker.py
- Smart chunking preserving semantic boundaries
- Type-specific strategies (text, table, image)
- MultimodalChunk class

---

## 5. Frontend Architecture

### 5.1 templates/index.html
- Terminal-themed dark interface with green accents
- Welcome screen with ASCII art
- Chat interface with message bubbles
- File upload with drag-and-drop
- Images bar for uploaded images
- Status indicators (ready, processing, error)

### 5.2 static/script.js
- File upload handling
- Image upload and processing
- Chat message sending
- Citation rendering (text, table, image)
- Toast notifications

### 5.3 static/style.css
- Terminal-style aesthetics
- Color palette: dark background, green accents
- Responsive design
- Citation styling with badges

---

## 6. Configuration

### Key Settings (in app.py)
```python
CHUNK_SIZE = 1000          # Text chunk size
CHUNK_OVERLAP = 200        # Chunk overlap
MAX_CITATIONS = 10         # Max citations per answer
SIMILARITY_THRESHOLD = 0.3 # Minimum relevance score
USE_MULTIMODAL_PDF = True  # Toggle for advanced PDF processing
```

### Dependencies
- flask, flask-cors, werkzeug
- langchain-core, langchain-community, langchain-text-splitters
- pypdf, python-docx, docx2txt
- pymupdf (multimodal PDF)
- sentence-transformers
- transformers, torch, pillow
- pytesseract, pdf2image
- unstructured

---

## 7. Integration Plans

### 7.1 Canvas LTI Integration (Future)
- Register as LTI 1.3 tool in Canvas
- Implement LTI launch handler
- Deep linking for content selection
- Grade passback functionality
- OAuth2 for Canvas API access

### 7.2 NVIDIA DLI Integration (Future)
- DLI API integration for course materials
- Student progress tracking
- GPU resource allocation
- Certificate generation

### 7.3 Deployment Requirements
- Python 3.9+
- 20GB+ disk space for models
- GPU recommended for BLIP-2
- Production: PostgreSQL, Redis, load balancing

---

## 8. Project Files Structure

```
VirtualTeachingAssistant_T18/
├── app.py                      # Main Flask application (1377 lines)
├── embedding_manager.py        # Text embeddings (764 lines)
├── vector_store.py             # Vector storage (1022 lines)
├── citation_tracker.py         # Citation tracking (830 lines)
├── answer_generator.py         # Answer generation (764 lines)
├── pdf_extractor.py            # PDF extraction (450+ lines)
├── image_analyzer.py           # Image analysis (300+ lines)
├── multimodal_chunker.py      # Smart chunking (250+ lines)
├── multimodal_processor.py     # Multimodal orchestration
├── document_loader.py          # Document loading
├── enhanced_rag_pipeline.py   # RAG pipeline
├── NemotronNano.py             # Vision model wrapper
├── vectordb.py                # Vector database utilities
├── requirements.txt           # Python dependencies
├── README.md                   # Basic documentation
├── TRADEBUZZ_TECHNICAL_DOCUMENTATION.md  # Full technical docs
├── Sprint2_Overview.md         # Sprint documentation
├── IMPLEMENTATION_SUMMARY.md   # Implementation details
├── DEBUGGING_IMPROVEMENTS_SUMMARY.md  # Bug fixes
├── sprint_report_template.md   # Sprint report format
├── templates/
│   └── index.html             # Frontend HTML
├── static/
│   ├── style.css              # Styling
│   ├── script.js              # Frontend JavaScript
│   └── extracted_images/      # Extracted PDF images
├── plans/
│   ├── multimodal_enhancement_plan.md
│   ├── advanced_multimodal_pdf_spec.md
│   └── image_upload_implementation_plan.md
└── extracted/                 # Demo extracted content
    └── images/                # Sample extracted images
```

---

## 9. Key Implementation Achievements

✅ Multimodal PDF processing (text, tables, images)  
✅ BLIP-2 image captioning  
✅ Tesseract OCR configuration  
✅ Whisper audio transcription support  
✅ Sentence transformer embeddings  
✅ In-memory vector similarity search  
✅ Comprehensive citation system  
✅ Terminal-themed responsive UI  
✅ Graceful fallback mechanisms  
✅ Error handling and logging  

---

## 10. Known Limitations

- **External Knowledge**: Answers strictly from uploaded documents only
- **Real-time Collaboration**: Single-user design
- **Persistent Storage**: In-memory (data lost on restart)
- **User Authentication**: Not implemented
- **File Size**: 50MB for documents, 10MB for images
- **Language**: Primarily English-focused
- **Vision API**: Requires NVIDIA API key

---

## 11. Next Steps

1. Complete Docker containerization
2. Implement Canvas LTI integration
3. Add user authentication and sessions
4. Implement persistent storage (PostgreSQL/ChromaDB)
5. Add multi-institution support
6. Improve performance for large documents

---

*Document Generated: 2026-03-12*  
*Project Status: Active Development*
