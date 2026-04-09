# TradeBuzz-1 Virtual Teaching Assistant - Comprehensive Technical Documentation

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Project Scope](#project-scope)
4. [Frontend-Backend Integration](#frontend-backend-integration)
5. [Backend Services and Functions](#backend-services-and-functions)
6. [Configuration and Environment](#configuration-and-environment)
7. [Data Flow and State Management](#data-flow-and-state-management)
8. [Security Considerations](#security-considerations)
9. [Deployment and Operations](#deployment-and-operations)

---

## Executive Summary

### Project Overview
**TradeBuzz-1 Virtual Teaching Assistant (VTA)** is a web-based Retrieval-Augmented Generation (RAG) system that enables users to upload documents (PDF, Word, Text, Audio, Images) and ask questions about their content. The system provides accurate answers with proper citations, including page numbers and verbatim text from source documents.

**Primary Objectives:**
- Provide a document Q&A system grounded exclusively in uploaded content
- Support multiple document formats with multimodal capabilities
- Ensure transparency through proper citation and reasoning
- Maintain honesty by clearly indicating when information is not found

**Key Features:**
- Multi-format document support (PDF, DOCX, TXT, MP3, WAV, OGG, M4A, FLAC, PNG, JPG, JPEG, WEBP, GIF, BMP)
- Multimodal processing: text extraction, tables, images with OCR
- Vector-based semantic search using sentence-transformers
- Answer generation with confidence scoring
- Comprehensive citation tracking with location precision
- Terminal-style minimalist UI with real-time chat interaction

**Technology Stack:**
- **Backend:** Python 3.9+, Flask 2.3+, Flask-CORS
- **Frontend:** HTML5, CSS3, Vanilla JavaScript (no frameworks)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **Document Processing:** LangChain, PyPDF, python-docx, unstructured
- **Vector Store:** In-memory numpy-based with optional ChromaDB
- **Vision AI:** NVIDIA Nemotron-Nano API (cloud-based)
- **Audio Transcription:** OpenAI Whisper (optional)
- **OCR:** pytesseract, pdf2image

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Browser)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Terminal-style UI (HTML/CSS/JS)                     │  │
│  │  - File upload (documents & images)                  │  │
│  │  - Chat interface                                    │  │
│  │  - Citation display                                  │  │
│  └───────────────────────┬──────────────────────────────┘  │
└───────────────────────────│──────────────────────────────────┘
                            │ REST API (JSON)
                            │ HTTPS/HTTP
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
│  └───────────────────────┬──────────────────────────────┘  │
│                          │                                  │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │  Core Modules                                        │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │  │
│  │  │ Document    │ │ Embedding   │ │ Vector      │   │  │
│  │  │ Loader      │ │ Manager     │ │ Store       │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │  │
│  │  │ Citation    │ │ Answer      │ │ Multimodal  │   │  │
│  │  │ Tracker     │ │ Generator   │ │ Processor   │   │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ sentence-     │   │ NVIDIA        │   │ OpenAI        │
│ transformers  │   │ Nemotron      │   │ Whisper       │
│ (local)       │   │ (cloud API)   │   │ (optional)    │
└───────────────┘   └───────────────┘   └───────────────┘
```

### Module Interdependencies

```
app.py (Main Application)
│
├─> RAGApplicationState (Global State Manager)
│   ├─> SimpleDocumentProcessor / MultiFileLoader
│   ├─> SimpleEmbeddingManager / EmbeddingManager
│   ├─> SimpleVectorStore / InMemoryVectorStore
│   └─> SimpleAnswerGenerator / AnswerGenerator
│
├─> process_audio_file() → whisper (optional)
├─> process_image_file() → NemotronNano (cloud API)
└─> Flask Routes → API endpoints
```

---

## Project Scope

### Primary Objectives
1. **Document Ingestion**: Accept and process multiple file formats with automatic format detection
2. **Content Extraction**: Extract text, tables, and images with OCR capabilities
3. **Semantic Indexing**: Create vector embeddings for efficient similarity search
4. **Question Answering**: Retrieve relevant context and generate accurate answers
5. **Citation Generation**: Provide verifiable citations with precise location information
6. **Honest Responses**: Clearly indicate when information is not found in documents

### Key Features

#### Document Support
- **Text Files**: `.txt` (plain text)
- **PDF Documents**: `.pdf` with text, table, and image extraction
- **Word Documents**: `.docx` (Microsoft Word)
- **Audio Files**: `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac` (via Whisper transcription)
- **Image Files**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` (via vision model)

#### Processing Capabilities
- **Chunking Strategy**: Recursive character splitting with configurable size (default: 1000 chars) and overlap (default: 200 chars)
- **Embedding Model**: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- **Similarity Metric**: Cosine similarity
- **Multimodal Processing**: Unstructured library for PDF element extraction
- **OCR**: pytesseract for image text extraction
- **Table Preservation**: Structured table data in Markdown format

#### Answer Generation
- **Confidence Levels**: High (≥0.7), Medium (≥0.4), Low (≥0.2), None (<0.2)
- **Answer Types**: found, not_found, partial, ambiguous
- **Citation Limit**: Configurable max citations (default: 10)
- **Similarity Threshold**: Minimum score for relevance (default: 0.3)

### Explicit Boundaries

#### Out of Scope
- **External Knowledge**: System does NOT use general knowledge; answers are strictly from uploaded documents
- **Real-time Collaboration**: No multi-user collaboration features
- **Document Editing**: No document modification capabilities
- **Advanced Analytics**: No document analytics or insights beyond Q&A
- **Persistent Storage**: In-memory vector store (data lost on restart) unless ChromaDB is configured
- **User Authentication**: No user accounts or authentication system
- **File Versioning**: No version control for documents
- **Batch Processing**: No scheduled or batch document processing

#### Limitations
- **File Size**: Maximum 50MB for documents, 10MB for images
- **Concurrent Users**: Single-user design (Flask development server)
- **Language Support**: Primarily English (embedding model is English-focused)
- **Vision API**: Requires NVIDIA API key and internet connection
- **Audio Processing**: Requires Whisper installation for transcription

---

## Frontend-Backend Integration

### API Endpoints

#### 1. Health Check
```
GET /api/health
```
**Purpose:** Check system status and component availability

**Request:** None

**Response:**
```json
{
  "status": "ok",
  "rag_initialized": true,
  "files_uploaded": 3,
  "sentence_transformers": true,
  "langchain": true,
  "whisper": false
}
```

**Error Codes:** None (always returns 200)

---

#### 2. Initialize RAG
```
POST /api/initialize
```
**Purpose:** Initialize the RAG application components

**Request:** Empty body

**Response:**
```json
{
  "success": true,
  "message": "RAG application initialized",
  "sentence_transformers": true,
  "langchain": true,
  "whisper": false
}
```

**Error Codes:**
- `500`: Initialization failed

---

#### 3. Upload File
```
POST /api/upload
Content-Type: multipart/form-data
```
**Purpose:** Upload and process documents (PDF, DOCX, TXT, audio)

**Request Parameters:**
- `file` (required): File to upload

**Response (Success):**
```json
{
  "success": true,
  "file_id": "abc123def456",
  "file_name": "document.pdf",
  "file_type": "pdf",
  "chunks_created": 24,
  "error": null
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "File type not allowed"
}
```

**Status Codes:**
- `200`: File uploaded and processed successfully
- `400`: Invalid file, unsupported type, or processing error
- `500`: Server error

**Processing Flow:**
1. Validate file type and size
2. Save to uploads directory with unique ID
3. Detect file extension
4. Load document using appropriate LangChain loader
5. Chunk document using RecursiveCharacterTextSplitter
6. Generate embeddings for each chunk
7. Add to vector store
8. Store file metadata in `app_state.uploaded_files`

---

#### 4. Upload Image
```
POST /api/upload/image
Content-Type: multipart/form-data
```
**Purpose:** Upload and analyze images using vision model

**Request Parameters:**
- `file` (required): Image file to upload

**Response:**
```json
{
  "success": true,
  "file_id": "xyz789abc123",
  "file_path": "/uploads/xyz789_image.jpg",
  "file_name": "image.jpg",
  "file_type": "image",
  "processing_mode": "vision",
  "description": "A detailed description of the image content...",
  "error": null
}
```

**Status Codes:**
- `200`: Image uploaded (analysis may have failed but file is kept)

**Notes:**
- Image is always kept on server even if analysis fails
- Description may contain error message if analysis failed
- File stored in `app_state.uploaded_images`

---

#### 5. Query System
```
POST /api/query
Content-Type: application/json
```
**Purpose:** Ask a question about uploaded documents/images

**Request Body:**
```json
{
  "question": "What is the main topic?",
  "max_results": 5
}
```

**Response (Success with Documents):**
```json
{
  "success": true,
  "answer": "Based on the uploaded documents:\n\nThe main topic is...\n\nSources:\n[1] document.pdf (Page 3, Chunk 1)\n    \"The main topic of this document is...\"",
  "citations": [
    {
      "source_file": "document.pdf",
      "page_number": 3,
      "chunk_index": 0,
      "similarity_score": 0.87,
      "verbatim": "The main topic of this document is...",
      "full_text": "Full chunk content...",
      "source_type": "document",
      "location": "Page 3, Chunk 1"
    }
  ],
  "answer_type": "found",
  "confidence": "high",
  "has_images": false
}
```

**Response (Success with Images Only):**
```json
{
  "success": true,
  "answer": "I analyzed the following uploaded images:\n\n### Image 1: chart.png\nDescription of image...\n\n---\n\n**Your question:** What does the chart show?\n\n",
  "citations": [],
  "source_type": "images"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "No documents or images uploaded. Please upload files first."
}
```

**Status Codes:**
- `200`: Query processed successfully
- `400`: Invalid request or no documents/images
- `500`: Server error

**Processing Logic:**
1. Check for uploaded images and/or documents
2. If only images: return concatenated descriptions
3. If documents: perform RAG pipeline
   - Embed query
   - Search vector store
   - Generate answer with citations
4. Include image metadata if both types exist

---

#### 6. List Files
```
GET /api/files
```
**Purpose:** Retrieve list of uploaded documents

**Response:**
```json
{
  "success": true,
  "files": [
    {
      "file_id": "abc123",
      "filename": "document.pdf",
      "file_type": "pdf",
      "chunks": 24,
      "upload_time": "2025-03-10T14:30:00"
    }
  ],
  "total_files": 1
}
```

---

#### 7. List Images
```
GET /api/images
```
**Purpose:** Retrieve list of uploaded images

**Response:**
```json
{
  "success": true,
  "images": [
    {
      "file_id": "xyz789",
      "file_name": "chart.png",
      "upload_time": "2025-03-10T14:35:00",
      "description": "A bar chart showing..."
    }
  ]
}
```

---

#### 8. Delete Image
```
DELETE /api/images/<file_id>
```
**Purpose:** Remove a specific uploaded image

**Response:**
```json
{
  "success": true,
  "message": "Image deleted"
}
```

**Status Codes:**
- `200`: Image deleted
- `404`: Image not found

---

#### 9. Clear All Documents
```
POST /api/clear
```
**Purpose:** Remove all uploaded documents and reset vector store

**Response:**
```json
{
  "success": true,
  "message": "All documents cleared"
}
```

---

#### 10. Serve Static Files
```
GET /static/<path>
GET /
```
**Purpose:** Serve frontend assets and main page

**Response:** HTML, CSS, or JavaScript files

---

### Request/Response Schemas

#### Document Upload Schema
```typescript
interface DocumentUploadResponse {
  success: boolean;
  file_id: string;          // Unique identifier
  file_name: string;        // Original filename
  file_type: string;        // Extension without dot
  chunks_created: number;   // Number of chunks created
  error: string | null;     // Error message if failed
}
```

#### Query Request Schema
```typescript
interface QueryRequest {
  question: string;         // User's question
  max_results?: number;     // Max chunks to retrieve (default: 5)
}
```

#### Query Response Schema
```typescript
interface QueryResponse {
  success: boolean;
  answer: string;           // Generated answer text
  citations: Citation[];    // Source citations
  answer_type: 'found' | 'not_found' | 'partial' | 'ambiguous';
  confidence: 'high' | 'medium' | 'low' | 'none';
  has_images?: boolean;     // Whether images are also uploaded
  error?: string;           // Error message if failed
}

interface Citation {
  source_file: string;
  page_number: number | string;
  chunk_index: number;
  similarity_score: number;  // 0.0 to 1.0
  verbatim: string;          // Truncated text preview
  full_text: string;         // Complete chunk content
  source_type: 'document' | 'image';
  location: string;          // Human-readable location
}
```

---

### State Management Patterns

#### Global State (`app_state`)
The application uses a singleton pattern with a global `RAGApplicationState` instance:

```python
class RAGApplicationState:
    - embedding_manager: EmbeddingManager
    - vector_store: VectorStore
    - document_processor: DocumentProcessor
    - answer_generator: AnswerGenerator
    - uploaded_files: Dict[file_id, file_info]
    - uploaded_images: Dict[file_id, image_info]
    - is_initialized: bool
```

**Initialization:** Auto-initialized on first request or at startup (`if __name__ == '__main__'`)

**Thread Safety:** Not thread-safe (development server only). For production, would need:
- Flask with WSGI server (Gunicorn/uWSGI)
- Session-based or database-backed state
- Lock mechanisms for concurrent access

#### Frontend State (JavaScript)
```javascript
let uploadedFiles = [];     // Track uploaded documents
let uploadedImages = [];    // Track uploaded images
let isUploading = false;    // Upload lock
let isProcessing = false;   // Query lock
```

**State Synchronization:**
- On page load: `loadFiles()` and `loadImages()` fetch from server
- After upload: Update local arrays and UI
- After clear: Reset local arrays

---

## Backend Services and Functions

### Core Modules

#### 1. Document Loader (`document_loader.py`)

**Purpose:** Load and chunk documents from various file formats

**Key Classes:**

##### `DocumentMetadata`
- **Attributes:**
  - `source`: Full file path
  - `filename`: File name
  - `file_type`: Extension
  - `mime_type`: MIME type
  - `file_size`: Size in bytes
  - `created_date`, `modified_date`: Timestamps
  - `document_id`: Unique SHA256-based ID (16 chars)
  - `chunk_count`: Number of chunks

##### `ChunkMetadata`
- **Attributes:**
  - `chunk_id`: Unique chunk identifier
  - `document_id`: Parent document ID
  - `source_file`, `source_path`
  - `char_start`, `char_end`: Character positions
  - `chunk_index`: Position in document

##### `MultiFileLoader`
- **Methods:**
  - `__init__(chunk_size=1000, chunk_overlap=100, encoding='utf-8')`
  - `is_supported(file_path) -> bool`
  - `get_file_info(file_path) -> dict`
  - `load_file(file_path) -> List[Document]`
  - `load_directory(directory_path, pattern, recursive) -> dict`

**Supported Formats:**
- `.txt` → TextLoader
- `.pdf` → PyPDFLoader
- `.docx` → Docx2txtLoader
- `.html`, `.htm` → UnstructuredHTMLLoader
- `.md`, `.markdown` → UnstructuredMarkdownLoader

**Chunking:** RecursiveCharacterTextSplitter with separators: `["\n\n", "\n", ". ", " ", ""]`

---

#### 2. Embedding Manager (`embedding_manager.py`)

**Purpose:** Generate and manage text embeddings

**Key Classes:**

##### `MockEmbeddings` (Fallback)
- Generates deterministic hash-based embeddings
- Used when no embedding provider is available
- **Not for production** (no semantic meaning)

##### `SentenceTransformerEmbeddings`
- **Model:** `all-MiniLM-L6-v2` (default) or `all-mpnet-base-v2` or multilingual
- **Dimensions:** 384 or 768
- **Device:** Auto-detects CUDA, MPS, or CPU
- **Methods:**
  - `embed_documents(texts: List[str]) -> List[List[float]]`
  - `embed_query(text: str) -> List[float]`
  - `get_embedding_dimension() -> int`

##### `OpenAIEmbeddingsWrapper`
- **Models:** `text-embedding-3-small` (1536 dim), `text-embedding-3-large` (3072 dim), `text-embedding-ada-002` (1536 dim)
- **API Key:** From parameter or `OPENAI_API_KEY` environment variable
- **Methods:** Same as above

##### `EmbeddingManager` (Main)
- **Provider Selection:** `sentence-transformers`, `openai`, or `mock`
- **Initialization:**
  ```python
  EmbeddingManager(
      provider='sentence-transformers',
      model_name='all-MiniLM-L6-v2',
      api_key=None,  # For OpenAI
      device=None,   # Auto-detect
      cache_folder=None
  )
  ```
- **Methods:**
  - `embed_documents(texts)`
  - `embed_query(text)`
  - `get_embedding_dimension()`

---

#### 3. Vector Store (`vector_store.py`)

**Purpose:** Store and retrieve document chunks with embeddings

**Key Classes:**

##### `DocumentChunk`
- **Attributes:**
  - `chunk_id`, `document_id`, `content`, `embedding`
  - `metadata`, `file_name`, `file_path`, `file_type`
  - `char_start`, `char_end`, `chunk_index`
- **Methods:**
  - `from_langchain_doc(doc, embedding, chunk_id)`
  - `to_dict()`
  - `to_langchain_doc()`

##### `InMemoryVectorStore`
- **Storage:** Numpy arrays for efficient similarity search
- **Indexing:** Metadata index for fast filtering by file name, document ID, file type
- **Methods:**
  - `__init__(dimension=384)`
  - `add_chunks(chunks: List[DocumentChunk])`
  - `similarity_search(query_embedding, k=4, filter_metadata=None) -> List[DocumentChunk]`
  - `get_chunk_by_id(chunk_id)`
  - `get_chunks_by_file(file_name)`
  - `get_chunks_by_document(document_id)`
  - `get_chunk_count()`

**Similarity Algorithm:** Cosine similarity
```python
# Normalize vectors
normalized_embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
normalized_query = query / np.linalg.norm(query)
# Compute dot product
similarities = np.dot(normalized_embeddings, normalized_query)
```

**Optional Backend:** ChromaDB (if installed) for persistent storage

---

#### 4. Citation Tracker (`citation_tracker.py`)

**Purpose:** Track and format citations for retrieved content

**Key Classes:**

##### `CitationSource`
- **Attributes:**
  - `chunk_id`, `document_id`, `source_file`, `source_path`
  - `file_type`, `content`, `chunk_index`
  - `char_start`, `char_end`, `similarity_score`, `metadata`
- **Methods:**
  - `from_chunk(chunk, similarity_score)`: Create from LangChain Document
  - `get_citation_id()`: MD5 hash of document+chunk (8 chars)
  - `get_file_display_name()`
  - `get_location_string()`: Returns "Page X" or "Chunk X"
  - `to_dict()`

##### `CitationFormatter`
- **Styles:** `numbered`, `apa`, `inline`, `verbatim`
- **Methods:**
  - `format_citation(source, style, include_score, max_content_length) -> str`
  - `format_citations_list(sources, style, include_scores) -> str`

##### `CitationTracker`
- **Purpose:** Manage collection of citations
- **Attributes:**
  - `max_citations`: Limit (default 10)
  - `citations`: List of CitationSource objects
  - `_source_index`: Dict for duplicate detection
  - `formatter`: CitationFormatter instance
  - `stats`: Tracking statistics
- **Methods:**
  - `add_citation(source, similarity_score) -> CitationSource`
  - `get_citations() -> List[CitationSource]`
  - `format_citations(style) -> str`
  - `clear()`

---

#### 5. Answer Generator (`answer_generator.py`)

**Purpose:** Generate answers from retrieved context with proper citations

**Key Classes:**

##### `AnswerContext`
- **Attributes:**
  - `query`, `retrieved_chunks`, `relevance_scores`
  - `source_files`, `total_chunks`
  - `max_score`, `avg_score` (computed)
- **Methods:**
  - `has_relevant_content(threshold) -> bool`
  - `get_best_score() -> float`
  - `get_answer_confidence() -> str`

##### `GeneratedAnswer`
- **Attributes:**
  - `answer_type`: `found`, `not_found`, `partial`, `ambiguous`
  - `answer_text`, `reasoning`
  - `citations: List[CitationSource]`
  - `confidence`: `high`, `medium`, `low`, `none`
  - `context_used: bool`
- **Methods:**
  - `to_dict()`
  - `format_for_display(style='detailed') -> str`

##### `AnswerGenerator` (Main)
- **Configuration:**
  ```python
  AnswerGenerator(
      include_reasoning=True,
      min_confidence_threshold=0.2,
      max_citations=5,
      llm_provider=None  # Future: integrate LLM for synthesis
  )
  ```
- **Main Method:**
  - `generate(query, retrieved_results, total_documents) -> GeneratedAnswer`
- **Private Methods:**
  - `_generate_not_found_answer(query, reason, total_docs, results)`
  - `_generate_found_answer(query, results, max_score)`

**Answer Generation Logic:**
1. Check if any results retrieved
2. Check max similarity score against threshold
3. If below threshold → `not_found` with honest message
4. If above threshold → construct answer from top results
5. Build citations with verbatim quotes
6. Determine confidence level from max score

---

#### 6. Multimodal Processor (`multimodal_processor.py`)

**Purpose:** Extract structured content from complex PDFs

**Key Classes:**

##### `MultimodalElement`
- **Attributes:**
  - `element_id`, `element_type` (text, table, image, ocr, title, header, footer)
  - `content`, `page_number`, `coordinates` (x1, y1, x2, y2)
  - `source_file`, `caption`, `metadata`
- **Methods:**
  - `get_location_string()`
  - `to_dict()`
  - `to_langchain_document()`: Convert to LangChain Document with enhanced metadata

##### `TableData`
- **Attributes:** `table_id`, `headers`, `rows`, `page_number`, `caption`
- **Methods:**
  - `to_markdown()`: Convert to Markdown table format
  - `to_dict()`

##### `MultimodalDocumentProcessor`
- **Configuration:**
  ```python
  MultimodalDocumentProcessor(
      extract_images=True,
      extract_tables=True,
      ocr_images=True,
      strategy='hi_res',
      infer_table_structure=True
  )
  ```
- **Strategies:** `auto`, `fast`, `hi_res`, `ocr_only`
- **Main Method:** `process_pdf(file_path) -> List[MultimodalElement]`
- **Processing Pipeline:**
  1. Use `unstructured.partition.pdf` to extract elements
  2. Separate by type (Text, Table, Image, etc.)
  3. Run OCR on images if enabled
  4. Associate captions with nearby elements
  5. Return ordered list by page position

**Dependencies:**
- `unstructured` (required)
- `pytesseract` + `Pillow` (for OCR)
- `pdf2image` (for image extraction from PDF)

---

#### 7. Vision Model (`NemotronNano.py`)

**Purpose:** Generate descriptions for uploaded images using NVIDIA's Nemotron-Nano vision model

**External API:** NVIDIA API endpoint `https://integrate.api.nvidia.com/v1/chat/completions`

**Key Functions:**

##### `chat_with_media(infer_url, media_files, query, stream, max_retries, timeout)`
- **Purpose:** Send request to vision model with retry logic
- **Parameters:**
  - `media_files`: List of file paths (images or videos)
  - `query`: Text prompt
  - `stream`: Not used (always False)
  - `max_retries`: Default 3
  - `timeout`: Default 60 seconds
- **Returns:** `requests.Response` object
- **Retry Logic:** Exponential backoff (1s, 2s, 4s)
- **Model:** `nvidia/nemotron-nano-12b-v2-vl`

##### `GetDescriptionFromLLM(image_path, max_retries, timeout) -> str`
- **Wrapper function** for easy image description
- **Prompt:** "Describe in detail what you see in the image..."
- **Returns:** Description string or error message
- **Error Handling:** Timeout, connection errors, API failures

**Configuration:**
- **API Key:** Environment variable `NM_API_KEY` (stored in `.env` file)
- **Base URL:** `https://integrate.api.nvidia.com/v1/chat/completions`
- **Parameters:** `max_tokens=4096`, `temperature=1`, `top_p=1`

**Supported Formats:** PNG, JPG, JPEG, WEBP, MP4, WEBM, MOV

---

#### 8. Simple Standalone Classes (in `app.py`)

For fallback when full modules aren't available:

##### `SimpleDocumentProcessor`
- Minimal document loading with LangChain
- Methods: `load_pdf()`, `load_docx()`, `load_text()`, `load_document()`, `chunk_documents()`

##### `SimpleEmbeddingManager`
- Wrapper around `sentence-transformers`
- Mock embeddings fallback using hash-based vectors

##### `SimpleVectorStore`
- In-memory numpy-based store
- Cosine similarity search
- No metadata indexing

##### `SimpleAnswerGenerator`
- Basic answer generation without LLM
- Returns concatenated context or "not found" messages

---

### Supporting Functions (in `app.py`)

#### File Processing
- `process_uploaded_file(file_path, file_id) -> Dict`: Process document files
- `process_image_file(file_path, file_id) -> Dict`: Process images with vision model
- `process_audio_file(file_path) -> Dict`: Transcribe audio with Whisper

#### Query Processing
- `retrieve_and_answer(query, max_results) -> Dict`: Full RAG pipeline
  1. Embed query
  2. Search vector store
  3. Generate answer
  4. Build citations

#### Validation
- `allowed_file(filename) -> bool`: Check document extensions
- `allowed_image(filename) -> bool`: Check image extensions
- `validate_image_file(file, max_size) -> Dict`: Comprehensive image validation

#### Utilities
- `generate_file_id() -> str`: MD5 hash of timestamp (12 chars)
- `get_file_extension(filename) -> str`

---

## Configuration and Environment

### Flask Configuration (`app.py`)

```python
# Upload Settings
app.config['UPLOAD_FOLDER'] = './uploads'  # Relative to app.py
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Allowed Extensions
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'txt', 'mp3', 'wav', 'ogg', 'm4a', 'flac'}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'tif'}
app.config['ALLOWED_EXTENSIONS'] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

# Image-specific Limits
app.config['MAX_IMAGE_SIZE'] = 10 * 1024 * 1024  # 10MB
app.config['ALLOWED_IMAGE_EXTENSIONS'] = IMAGE_EXTENSIONS

# RAG Parameters
app.config['CHUNK_SIZE'] = 1000
app.config['CHUNK_OVERLAP'] = 200
app.config['MAX_CITATIONS'] = 10
app.config['SIMILARITY_THRESHOLD'] = 0.3
```

### Environment Variables

#### Required
- **`NM_API_KEY`**: NVIDIA API key for Nemotron vision model
  - **Location:** `.env` file (gitignored)
  - **Used by:** `NemotronNano.py`
  - **Security:** High - Direct access to paid API

#### Optional
- **`OPENAI_API_KEY`**: OpenAI API key for embeddings (if using OpenAI)
  - **Used by:** `embedding_manager.py`
  - **Security:** High - Access to OpenAI billing

### Configuration Files

#### `.env` (Gitignored)
```
NM_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
**Security:** Never commit to version control. Contains sensitive API credentials.

#### `requirements.txt`
Comprehensive Python dependencies with pinned versions:
- **Web:** Flask 2.3+, Flask-CORS, Werkzeug
- **ML:** torch 2.10.0, transformers 5.1.0, sentence-transformers 2.2.0
- **Document Processing:** pypdf 6.7.0, python-docx, unstructured 0.20.2
- **Embeddings:** numpy 2.2.0
- **Vision:** google-cloud-vision, opencv-python, Pillow
- **Audio:** openai-whisper (commented out, optional)
- **Utilities:** python-magic, aiofiles, etc.

**Installation:**
```bash
pip install -r requirements.txt
```

---

## Data Flow and State Management

### Document Upload Flow

```
User Uploads File
       │
       ▼
[Frontend] FormData → POST /api/upload
       │
       ▼
[Backend] Flask Route /api/upload
       │
       ├─> Check if initialized → initialize()
       │
       ├─> Validate file type & size
       │
       ├─> Save to uploads/{file_id}_{filename}
       │
       ├─> process_uploaded_file()
       │   │
       │   ├─> Load document (MultiFileLoader.load_file)
       │   │   └─> Extract text, preserve metadata
       │   │
       │   ├─> Chunk documents (RecursiveCharacterTextSplitter)
       │   │   └─> Add chunk_index, document_id to metadata
       │   │
       │   ├─> Generate embeddings (EmbeddingManager.embed_documents)
       │   │   └─> sentence-transformers.encode()
       │   │
       │   └─> Add to vector store (InMemoryVectorStore.add_chunks)
       │       ├─> Store DocumentChunk objects
       │       ├─> Update embeddings numpy array
       │       └─> Index metadata
       │
       └─> Store file info in app_state.uploaded_files
       
       │
       ▼
[Response] JSON with file_id, chunks_created
       │
       ▼
[Frontend] Update filesBar, show toast
```

### Query Flow

```
User Enters Question
       │
       ▼
[Frontend] POST /api/query {question, max_results}
       │
       ▼
[Backend] Flask Route /api/query
       │
       ├─> Check for uploaded images/documents
       │
       ├─> If only images:
       │   └─> Concatenate image descriptions from uploaded_images
       │       └─> Return immediately
       │
       └─> If documents:
           │
           ▼
       retrieve_and_answer()
           │
           ├─> Embed query (EmbeddingManager.embed_query)
           │   └─> sentence-transformers.encode(query)
           │
           ├─> Vector search (InMemoryVectorStore.similarity_search)
           │   ├─> Normalize query embedding
           │   ├─> Compute cosine similarity with all chunks
           │   ├─> Get top-k indices
           │   └─> Add similarity_score to chunk metadata
           │
           ├─> Prepare retrieved_data list
           │   └─> Extract content, metadata, scores
           │
           ├─> Generate answer (AnswerGenerator.generate)
           │   ├─> Check if max_score >= threshold
           │   ├─> If below: return not_found answer
           │   └─> If above: construct answer from context
           │
           ├─> Build citations
           │   └─> For each result: create CitationSource
           │       └─> Extract: file, page, chunk, score, verbatim
           │
           └─> Format final response
               └─> Append sources to answer text
       
       │
       ▼
[Response] JSON with answer, citations, confidence
       │
       ▼
[Frontend] Display message with citations
       └─> Render citation items with similarity percentages
```

### Image Processing Flow

```
User Uploads Image
       │
       ▼
POST /api/upload/image (or /api/upload auto-detects)
       │
       ├─> Validate image (type, size)
       │
       ├─> Save to uploads/{file_id}_{filename}
       │
       ├─> process_image_file()
       │   │
       │   └─> GetDescriptionFromLLM(image_path)
       │       │
       │       ├─> Encode image to base64
       │       │
       │       ├─> Build payload with multimodal message
       │       │   └─> Model: nvidia/nemotron-nano-12b-v2-vl
       │       │
       │       ├─> POST to NVIDIA API with retry (3 attempts)
       │       │   └─> Exponential backoff on timeout/error
       │       │
       │       └─> Extract description from response
       │           └─> result['choices'][0]['message']['content']
       │
       └─> Store in app_state.uploaded_images[file_id]
           └─> {file_path, file_name, description, has_error, error_message}
       
       │
       ▼
Return result (success flag + description or error)
       │
       ▼
Frontend shows image in imagesBar regardless of success
```

### State Lifecycle

#### Application Startup
```python
if __name__ == '__main__':
    app_state.initialize()  # Auto-initialize components
    app.run(host='0.0.0.0', port=5000, debug=True)
```

#### Per-Request State
- **Initialization Check:** If `not app_state.is_initialized`, call `initialize()`
- **Thread Safety:** None (development mode only)
- **State Reset:** `POST /api/clear` clears `uploaded_files` and reinitializes `vector_store`

#### File State
- **Documents:** `app_state.uploaded_files: Dict[file_id, info]`
  - Persists until server restart or `/api/clear`
  - `info` includes: `file_path`, `filename`, `file_type`, `document_id`, `chunks`, `upload_time`
- **Images:** `app_state.uploaded_images: Dict[file_id, info]`
  - Same persistence
  - `info` includes: `file_path`, `file_name`, `upload_time`, `description`, `has_error`, `error_message`

---

## Security Considerations

### API Keys and Secrets
- **`.env` file** contains `NM_API_KEY` - must be kept secret and gitignored
- **Never commit** API keys to version control
- **Rotate keys** periodically
- **Use environment-specific** keys (dev vs prod)

### File Upload Security
- **File Type Validation:** Both extension and MIME type checking
- **Size Limits:** 50MB for docs, 10MB for images
- **Filename Sanitization:** `werkzeug.utils.secure_filename()`
- **Path Traversal Prevention:** Files saved with `file_id_` prefix, no user-controlled paths
- **Directory Creation:** `os.makedirs(..., exist_ok=True)` safe

### Input Validation
- **JSON Schema:** Query requests validated for `question` presence
- **Type Coercion:** `max_results` from request (default 5)
- **SQL Injection:** Not applicable (no database)
- **XSS Prevention:** Frontend uses `escapeHtml()` for user content

### CORS
- **Flask-CORS** enabled with default permissive settings
- **Production:** Should restrict to specific origins
  ```python
  CORS(app, origins=["https://yourdomain.com"])
  ```

### Rate Limiting
- **Not implemented** - vulnerable to abuse
- **Recommendation:** Add Flask-Limiter or reverse proxy limits

### Authentication/Authorization
- **None** - system is completely open
- **Recommendation:** Add API keys or OAuth for production

### Data Privacy
- **All processing local** except:
  - Image analysis via NVIDIA API (images sent to external service)
  - Optional OpenAI embeddings (text sent to external API)
- **User Responsibility:** Inform users about external API usage
- **Data Retention:** Files stored indefinitely until manual clear or server restart

### Dependency Security
- **Pinned versions** in `requirements.txt` to prevent supply chain attacks
- **Regular updates** needed for security patches
- **Vulnerability scanning:** Use `safety check` or `pip-audit`

---

## Deployment and Operations

### Development Setup

1. **Clone and Install:**
   ```bash
   git clone <repository>
   cd VirtualTeachingAssistant_T18
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Unix
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   # Create .env file
   echo "NM_API_KEY=your_nvidia_api_key" > .env
   
   # Optional: OpenAI
   echo "OPENAI_API_KEY=your_openai_key" >> .env
   ```

3. **Run Application:**
   ```bash
   python app.py
   # Access at http://localhost:5000
   ```

### Production Deployment

**Not recommended** to use Flask development server in production. Use:

#### Option 1: Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### Option 2: uWSGI
```ini
[uwsgi]
module = app:app
master = true
processes = 4
socket = 127.0.0.1:5000
chmod-socket = 660
vacuum = true
die-on-term = true
```

#### Option 3: Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV FLASK_APP=app.py
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment-Specific Configurations

#### Development
- `debug=True` in `app.run()`
- `sentence-transformers` local model (no API costs)
- In-memory vector store (data lost on restart)
- CORS open to all

#### Production
- `debug=False`
- Consider persistent vector store (ChromaDB, Pinecone, Weaviate)
- Configure CORS origins
- Add authentication
- Set up reverse proxy (Nginx/Apache)
- Use WSGI server (Gunicorn/uWSGI)
- Enable HTTPS
- Implement rate limiting
- Set up logging to file/centralized system

### Monitoring and Logging

**Current Logging:**
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Log Levels:**
- `INFO`: Normal operations, file uploads, queries
- `WARNING`: Missing optional dependencies
- `ERROR`: Exceptions caught in routes, processing failures

**Recommendations:**
- Rotate logs with `RotatingFileHandler`
- Send logs to centralized system (ELK, Splunk, CloudWatch)
- Add structured logging (JSON format)
- Track metrics: upload count, query latency, error rates

### Scaling Considerations

**Current Limitations:**
- Single-threaded Flask dev server
- In-memory vector store (limited by RAM)
- No caching layer
- No database for persistence

**Horizontal Scaling:**
- **Challenge:** Global `app_state` not shared across processes
- **Solution:** Use external storage:
  - Vector database (ChromaDB, Pinecone, Weaviate)
  - File metadata in PostgreSQL/MySQL
  - Redis for session/cache
- **Load Balancer:** Nginx round-robin with sticky sessions

**Vertical Scaling:**
- Increase RAM for larger vector store
- Use GPU for embedding generation
- SSD for faster file I/O

### Backup and Recovery

**Files:**
- Uploaded files in `./uploads/` directory
- **Backup:** Regular filesystem backups
- **Retention:** Manual cleanup needed

**Vector Store:**
- In-memory only → lost on restart
- **Persistent option:** Configure ChromaDB
  ```python
  import chromadb
  client = chromadb.PersistentClient(path="./chroma_db")
  ```

---

## Appendix

### File Structure
```
VirtualTeachingAssistant_T18/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── .env                        # Environment variables (gitignored)
├── .gitignore                  # Git exclusions
├── uploads/                    # Uploaded files (created at runtime)
│
├── document_loader.py          # Multi-format document loading
├── embedding_manager.py        # Embedding generation
├── vector_store.py             # Vector storage & retrieval
├── citation_tracker.py         # Citation management
├── answer_generator.py         # Answer synthesis
├── multimodal_processor.py     # PDF multimodal extraction
├── NemotronNano.py             # Vision model integration
│
├── templates/
│   └── index.html              # Frontend HTML
├── static/
│   ├── style.css               # Terminal-style CSS
│   └── script.js               # Frontend JavaScript
│
├── extracted/                  # Sample extracted content (dev only)
│   └── images/
└── plans/
    └── image_upload_implementation_plan.md
```

### Technology Rationale

**Why sentence-transformers?**
- Free, local, no API costs
- Good quality for semantic search
- All-MiniLM-L6-v2: Fast (384 dim), good performance

**Why Flask?**
- Lightweight, easy to prototype
- Minimal boilerplate
- Good for single-developer projects

**Why In-Memory Vector Store?**
- Simplicity, no external dependencies
- Fast for small datasets (<100K chunks)
- Not suitable for production persistence

**Why NVIDIA Nemotron?**
- State-of-the-art vision model
- Competitive with GPT-4V, Claude 3
- Reasonable API pricing
- Supports both images and videos

### Future Enhancements

1. **Persistent Storage:** Integrate ChromaDB or Pinecone
2. **LLM Integration:** Use GPT-4 or Claude for better answer synthesis
3. **Multi-user Support:** User accounts, document ownership
4. **Advanced Chunking:** Semantic chunking, recursive splitting improvements
5. **Hybrid Search:** Combine vector + keyword (BM25) search
6. **Query Expansion:** Use query rewriting for better retrieval
7. **Relevance Feedback:** Learn from user feedback
8. **Batch Upload:** Process multiple files concurrently
9. **Document Management:** Delete individual files, versioning
10. **Analytics Dashboard:** Usage statistics, popular queries
11. **API Documentation:** OpenAPI/Swagger spec
12. **Testing:** Unit tests, integration tests, load tests
13. **CI/CD:** Automated testing and deployment
14. **Docker Compose:** Easy local development environment
15. **Rate Limiting:** Prevent abuse
16. **Authentication:** OAuth, API keys
17. **Audit Logging:** Track all user actions
18. **File Preprocessing:** OCR improvement, table extraction enhancement
19. **Audio Support:** Full Whisper integration
20. **Multilingual:** Support non-English documents

---

**Document Version:** 1.0  
**Last Updated:** 2025-03-10  
**Authors:** CPT_S 421 Development Team  
**Review Status:** Comprehensive technical analysis complete
