# Document Q&A - RAG Web Application

A web-based Retrieval-Augmented Generation (RAG) system that allows users to upload various document types (PDF, Word, Text, Audio) and ask questions about their content with proper citations.

## Features

- **Multi-format Document Support**: PDF, Word (.docx), Text (.txt), Audio (MP3, WAV, OGG, M4A, FLAC)
- **Multimodal Processing**: Extracts text, tables, images with OCR from PDFs
- **Vector Search**: Semantic similarity search using sentence-transformers
- **Answer Generation**: Uses local AI models (Ollama/GPT4All) or returns retrieved content
- **Proper Citations**: Every answer includes page numbers and verbatim text from source documents
- **Minimalist UI**: Clean interface with file upload and chat interaction

## Requirements

- Python 3.9+
- See `requirements.txt` for dependencies

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install audio transcription
pip install openai-whisper

# Optional: Install Ollama for local LLM
# See: https://github.com/ollama/ollama
```

## Running the Application

```bash
# Start the Flask server
python app.py

# The application will be available at http://localhost:5000
```

## Usage

1. **Open the application** in your browser at `http://localhost:5000`
2. **Upload documents** by clicking "Select Files" or drag-and-drop
3. **Ask questions** about the document content in the chat input
4. **View citations** - Each answer includes clickable citations with:
   - Source file name
   - Page number and location
   - Verbatim text from the source

## Project Structure

```
Multi_File_RAG/
├── app.py                  # Flask web application
├── templates/
│   └── index.html          # Frontend HTML
├── static/
│   ├── style.css           # Styles
│   └── script.js           # Frontend JavaScript
├── document_loader.py      # Document loading module
├── embedding_manager.py    # Text embeddings
├── vector_store.py         # Vector database
├── citation_tracker.py     # Citation tracking
├── answer_generator.py    # Answer generation
├── multimodal_processor.py # PDF processing
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

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

## Configuration

Key settings in `app.py`:

- `CHUNK_SIZE`: Text chunk size (default: 1000)
- `CHUNK_OVERLAP`: Chunk overlap (default: 200)
- `MAX_CITATIONS`: Max citations per answer (default: 10)
- `SIMILARITY_THRESHOLD`: Minimum similarity score (default: 0.3)

## Citation System

The system provides:

1. **Page Numbers**: Exact page where information was found
2. **Chunk Index**: Position within the document
3. **Similarity Score**: Relevance percentage
4. **Verbatim Text**: Exact text from source document
5. **Clickable Citations**: Users can click to reference

## Notes

- Answers are grounded ONLY in uploaded documents (no external knowledge)
- Audio files are transcribed using Whisper
- PDFs are processed for text, tables, and images with OCR
- The system maintains context through overlapping chunk strategy
