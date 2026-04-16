"""
Multi-File RAG Web Application
================================
A web-based RAG system that allows users to upload documents,
ask questions, and receive answers with proper citations.

Author: CPT_S 421 Development Team
Version: 1.0.0
"""

import os
import json
import logging
import uuid
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import threading
import queue
import time

# Authentication imports
import secrets
from functools import wraps

# Fix for Python 3.14 + google.protobuf compatibility
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

# Flask imports
from flask import Flask, request, jsonify, render_template, send_from_directory, abort, redirect, session
from flask_cors import CORS
from werkzeug.utils import secure_filename

# HTTP requests for Node.js API calls
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Loaded environment variables from .env")
except ImportError:
    logger.warning("python-dotenv not available, using system environment variables")

# ============================================================================
# UNIFIED DOCUMENT PROCESSOR (Gemini-powered)
# ============================================================================

UNIFIED_PROCESSOR_AVAILABLE = False
unified_processor = None

try:
    from unified_document_processor import UnifiedDocumentProcessor, create_processor
    UNIFIED_PROCESSOR_AVAILABLE = True
    logger.info("Unified document processor (Gemini-powered) available")
except ImportError as e:
    logger.warning(f"Unified document processor not available: {e}")

# ============================================================================
# FLASK APPLICATION SETUP
# ============================================================================

# Get base directory and set up template paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure Flask to use frontend templates
FRONTEND_TEMPLATES = os.path.join(BASE_DIR, '..', 'frontend', 'templates')
FRONTEND_STATIC = os.path.join(BASE_DIR, '..', 'frontend', 'static')
FRONTEND_INSTRUCTOR = os.path.join(BASE_DIR, '..', 'frontend', 'instructor')

app = Flask(__name__, 
            template_folder=FRONTEND_TEMPLATES,
            static_folder=FRONTEND_STATIC)

# Add instructor static files path
app.static_folder = FRONTEND_STATIC
app.static_url_path = '/static'

# Configure session secret key (required for Google OAuth)
app.secret_key = os.environ.get('SECRET_KEY', 'vta-session-secret-key-2026')

CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size (increased for audio/video)

# All audio extensions (comprehensive list)
AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac', 'wma', 'aiff', 'opus', 'webm', 'amr', '3gp', 'midi', 'mid', 'ra', 'ram', 'mp2', 'ac3'}

# Document extensions (text-based documents)
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'txt', 'doc', 'rtf', 'odt', 'csv', 'xlsx', 'xls', 'pptx', 'ppt'}

# Image extensions for vision model
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'tif', 'svg', 'ico', 'heic', 'heif', 'avif', 'jfif', 'pjpeg', 'pjp'}

# Combined extensions (all uploadable file types)
app.config['ALLOWED_EXTENSIONS'] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS

# Separate configs for type-specific limits
app.config['MAX_IMAGE_SIZE'] = 10 * 1024 * 1024  # 10MB for images
app.config['MAX_AUDIO_SIZE'] = 100 * 1024 * 1024  # 100MB for audio
app.config['ALLOWED_IMAGE_EXTENSIONS'] = IMAGE_EXTENSIONS
app.config['ALLOWED_AUDIO_EXTENSIONS'] = AUDIO_EXTENSIONS

app.config['CHUNK_SIZE'] = 1000
app.config['CHUNK_OVERLAP'] = 200
app.config['MAX_CITATIONS'] = 10
app.config['SIMILARITY_THRESHOLD'] = 0.3

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Extracted images directory (for saved image files from PDFs)
app.config['EXTRACTED_IMAGES_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'extracted_images')
os.makedirs(app.config['EXTRACTED_IMAGES_DIR'], exist_ok=True)

# Multimodal processing flag
# Set to True to extract images and tables from PDFs
app.config['USE_MULTIMODAL_PDF'] = True  # Toggle for advanced PDF processing

# ============================================================================
# DEPENDENCY CHECK
# ============================================================================

# Check and import dependencies
SENTENCE_TRANSFORMERS_AVAILABLE = False
LANGCHAIN_AVAILABLE = False
WHISPER_AVAILABLE = False
NEMOTRON_AVAILABLE = False

# Import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("sentence-transformers loaded successfully")
except ImportError as e:
    logger.warning(f"sentence-transformers not available: {e}")

# LangChain imports
try:
    from langchain_community.chat_models import ChatOllama
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema.output_parser import StrOutputParser
    from langchain.schema import Document
    LANGCHAIN_AVAILABLE = True
    logger.info("langchain loaded successfully")
except ImportError as e:
    logger.warning(f"langchain not available: {e}")

# Whisper for audio transcription
try:
    import whisper
    # Ensure ffmpeg is in PATH for whisper
    try:
        import shutil
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg_exe = get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        
        # Create a copy named ffmpeg.exe so whisper can find it
        ffmpeg_standard = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_standard):
            shutil.copy2(ffmpeg_exe, ffmpeg_standard)
        
        if ffmpeg_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
    except Exception as e:
        logger.warning(f"ffmpeg setup issue: {e}")
    
    WHISPER_AVAILABLE = True
    logger.info("whisper loaded successfully")
except ImportError as e:
    WHISPER_AVAILABLE = False
    logger.warning(f"whisper not available: {e}")

# Vision model imports - Nemotron for image description
try:
    import sys
    # Add current directory to path for imports
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from NemotronNano import GetDescriptionFromLLM, kSupportedList
    NEMOTRON_AVAILABLE = True
    logger.info("Vision model (Nemotron) loaded successfully")
except ImportError as e:
    logger.warning(f"Vision model not available: {e}")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("sentence-transformers available")
except ImportError:
    logger.warning("sentence-transformers not available")

# Use standalone implementations only (disable langchain)
LANGCHAIN_AVAILABLE = False
TEXT_SPLITTER_AVAILABLE = False
logger.info("Using standalone document processing (langchain disabled for compatibility)")

# Multimodal PDF processing imports
try:
    from pdf_extractor import PyMuPDFExtractor
    from multimodal_chunker import MultimodalChunker, create_chunks_from_pdf
    from image_analyzer import create_image_analyzer
    MULTIMODAL_AVAILABLE = True
    logger.info("Multimodal PDF processing available")
except ImportError as e:
    MULTIMODAL_AVAILABLE = False
    logger.warning(f"Multimodal processing not available: {e}")

# Multimodal relevance scoring import
RELEVANCE_SCORER_AVAILABLE = False
try:
    from multimodal_relevance_scorer import MultimodalRelevanceScorer, create_relevance_scorer
    RELEVANCE_SCORER_AVAILABLE = True
    logger.info("Multimodal relevance scorer available")
except ImportError as e:
    RELEVANCE_SCORER_AVAILABLE = False
    logger.warning(f"Multimodal relevance scorer not available: {e}")

try:
    import whisper
    WHISPER_AVAILABLE = True
    logger.info("Whisper available")
except ImportError:
    logger.warning("Whisper not available")


# ============================================================================
# TIMEOUT AND ERROR HANDLING UTILITIES
# ============================================================================

class TimeoutError(Exception):
    """Exception raised when an operation times out."""
    pass


def run_with_timeout(func, args=(), kwargs=None, timeout_seconds=120, default=None):
    """
    Run a function with a timeout. If the function takes too long, return default.
    
    Args:
        func: Function to run
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        timeout_seconds: Maximum time to wait (default 120 seconds)
        default: Value to return on timeout
    
    Returns:
        Function result or default value on timeout
    """
    if kwargs is None:
        kwargs = {}
    
    result_queue = queue.Queue()
    error_queue = queue.Queue()
    
    def target():
        try:
            result = func(*args, **kwargs)
            result_queue.put(('success', result))
        except Exception as e:
            error_queue.put(('error', e))
    
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        # Thread is still running - timeout occurred
        logger.warning(f"Operation timed out after {timeout_seconds} seconds: {func.__name__}")
        return default
    else:
        # Thread completed
        if not result_queue.empty():
            status, result = result_queue.get()
            return result
        if not error_queue.empty():
            status, error = error_queue.get()
            raise error
    
    return default


def safe_file_cleanup(file_path: str) -> bool:
    """
    Safely remove a file, ignoring errors.
    
    Args:
        file_path: Path to the file to remove
    
    Returns:
        True if file was removed, False otherwise
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
            return True
    except Exception as e:
        logger.warning(f"Failed to clean up file {file_path}: {e}")
    return False


# ============================================================================
# SIMPLE DOCUMENT PROCESSING (STANDALONE)
# ============================================================================

class SimpleDocumentProcessor:
    """Standalone document processor when RAG modules are not available."""
    
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # Don't initialize langchain text splitter - use simple chunking instead
        self.text_splitter = None
        
    def load_pdf(self, file_path: str) -> List[Any]:
        """Load PDF using pypdf directly (no langchain)."""
        try:
            from pypdf import PdfReader
            
            class TextDoc:
                def __init__(self, content, meta):
                    self.page_content = content
                    self.metadata = meta
            
            logger.info(f"Loading PDF: {file_path}")
            reader = PdfReader(file_path)
            docs = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    docs.append(TextDoc(
                        content=text,
                        meta={'source': file_path, 'page_number': i + 1}
                    ))
            
            logger.info(f"Loaded {len(docs)} pages from PDF using pypdf")
            return docs
            
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            return []
    
    def load_docx(self, file_path: str) -> List[Any]:
        """Load Word document using python-docx."""
        try:
            from docx import Document
            
            class TextDoc:
                def __init__(self, content, meta):
                    self.page_content = content
                    self.metadata = meta
            
            logger.info(f"Loading DOCX: {file_path}")
            doc = Document(file_path)
            full_text = []
            for para in doc.paragraphs:
                full_text.append(para.text)
            
            text = '\n'.join(full_text)
            if text.strip():
                return [TextDoc(text, {'source': file_path})]
            return []
            
        except Exception as e:
            logger.error(f"Error loading DOCX: {e}")
            return []
    
    def load_text(self, file_path: str) -> List[Any]:
        """Load text file directly."""
        try:
            class TextDoc:
                def __init__(self, content, meta):
                    self.page_content = content
                    self.metadata = meta
            
            logger.info(f"Loading text file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if text.strip():
                return [TextDoc(text, {'source': file_path})]
            return []
            
        except Exception as e:
            logger.error(f"Error loading text: {e}")
            return []
    
    def load_document(self, file_path: str) -> List[Any]:
        """Load document based on extension."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return self.load_pdf(file_path)
        elif ext == '.docx':
            return self.load_docx(file_path)
        elif ext == '.txt':
            return self.load_text(file_path)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []
    
    def chunk_documents(self, documents: List[Any]) -> List[Any]:
        """Chunk documents into smaller pieces using simple chunking."""
        if not documents:
            return []
        
        chunks = []
        
        for doc in documents:
            # Get the text content
            if hasattr(doc, 'page_content'):
                text = doc.page_content
            else:
                text = str(doc)
            
            # Get metadata
            metadata = {}
            if hasattr(doc, 'metadata'):
                metadata = doc.metadata.copy() if doc.metadata else {}
            
            # Simple chunking by characters
            chunk_size = self.chunk_size
            overlap = self.chunk_overlap
            
            for i in range(0, len(text), chunk_size - overlap):
                chunk_text = text[i:i + chunk_size]
                if chunk_text.strip():
                    # Create a simple chunk object
                    class Chunk:
                        def __init__(self, content, meta):
                            self.page_content = content
                            self.metadata = meta
                    
                    chunk_meta = metadata.copy()
                    chunk_meta['char_start'] = i
                    chunk_meta['char_end'] = i + len(chunk_text)
                    
                    chunks.append(Chunk(chunk_text, chunk_meta))
                    
                if i + chunk_size >= len(text):
                    break
        
        logger.info(f"Created {len(chunks)} chunks from {len(documents)} documents")
        return chunks


class SimpleEmbeddingManager:
    """Standalone embedding manager."""
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.dimension = 384
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Try loading with timeout using thread
                import queue
                import threading
                
                result_queue = queue.Queue()
                
                def load_model():
                    try:
                        model = SentenceTransformer(model_name)
                        result_queue.put(('success', model))
                    except Exception as e:
                        result_queue.put(('error', e))
                
                thread = threading.Thread(target=load_model, daemon=True)
                thread.start()
                thread.join(timeout=60)  # 60 second timeout for model loading
                
                if thread.is_alive():
                    logger.warning(f"Model loading timed out after 60 seconds, using mock embeddings")
                else:
                    if not result_queue.empty():
                        status, data = result_queue.get()
                        if status == 'success':
                            self.model = data
                            self.dimension = self.model.get_sentence_embedding_dimension()
                            logger.info(f"Loaded embedding model: {model_name}")
                        else:
                            logger.error(f"Error loading embedding model: {data}")
                    else:
                        logger.warning("Model loading returned no result, using mock embeddings")
            except Exception as e:
                logger.error(f"Error loading embedding model: {e}")
        else:
            logger.warning("Using mock embeddings")
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        if self.model:
            embedding = self.model.encode(text)
            return embedding.tolist()
        else:
            # Return mock embedding
            return [hash(c) % 100 / 100.0 for c in text[:384]] + [0.0] * (384 - len(text))
    
    def embed_documents(self, documents: List[Any]) -> List[List[float]]:
        """Embed multiple documents."""
        if not documents:
            return []
        
        texts = [doc.page_content for doc in documents]
        
        if self.model:
            embeddings = self.model.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        else:
            return [[hash(c) % 100 / 100.0 for c in text[:384]] + [0.0] * (384 - len(text)) for text in texts]
    
    def embed_documents_with_metadata(self, documents: List[Any]) -> Dict:
        """Embed documents and return with metadata."""
        embeddings = self.embed_documents(documents)
        metadatas = [doc.metadata for doc in documents]
        
        return {
            'embeddings': embeddings,
            'metadatas': metadatas
        }
    
    def get_embedding_dimension(self) -> int:
        return self.dimension


class SimpleVectorStore:
    """Standalone in-memory vector store."""
    
    def __init__(self, dimension=384):
        self.dimension = dimension
        self.documents = []
        self.embeddings = []
        self.metadatas = []
        
    def add_documents(self, documents: List[Any], embeddings: List[List[float]], metadatas: List[Dict]):
        """Add documents to the store."""
        self.documents.extend(documents)
        self.embeddings.extend(embeddings)
        self.metadatas.extend(metadatas)
        
    def similarity_search(self, query_embedding: List[float], k: int = 4) -> List[Any]:
        """Search for similar documents using cosine similarity."""
        if not self.embeddings:
            return []
        
        import numpy as np
        
        query = np.array(query_embedding)
        query_norm = np.linalg.norm(query)
        
        if query_norm == 0:
            return []
        
        # Calculate similarities
        embeddings = np.array(self.embeddings)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        
        normalized_embeddings = embeddings / norms
        normalized_query = query / query_norm
        
        similarities = np.dot(normalized_embeddings, normalized_query)
        
        # Get top k indices
        top_k_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_k_indices:
            if similarities[idx] > 0:
                doc = self.documents[idx].copy() if hasattr(self.documents[idx], 'copy') else self.documents[idx]
                if hasattr(doc, 'metadata'):
                    doc.metadata['similarity_score'] = float(similarities[idx])
                results.append(doc)
        
        return results


class SimpleAnswerGenerator:
    """Multimodal-aware answer generator with proper source citations."""
    
    def __init__(self, min_confidence=0.3):
        self.min_confidence = min_confidence
        
    def generate(self, query: str, retrieved_results: List[Dict], total_documents: int = 0):
        """
        Generate answer from retrieved results with multimodal source citations.
        
        Supports:
        - Text passages with page numbers
        - Audio segments with timestamps, speaker, and direct quotes
        - Table references with descriptions
        - Image references with descriptions
        """
        class Result:
            def __init__(self, answer_type, answer_text, reasoning, confidence):
                self.answer_type = answer_type
                self.answer_text = answer_text
                self.reasoning = reasoning
                self.confidence = confidence
        
        if not retrieved_results:
            return Result(
                answer_type='not_found',
                answer_text="I couldn't find relevant information in the uploaded documents.",
                reasoning="No documents found or no matching content.",
                confidence="none"
            )
        
        # Get best score
        scores = [r.get('similarity_score', r.get('relevance_score', 0)) for r in retrieved_results]
        best_score = max(scores) if scores else 0
        
        if best_score < self.min_confidence:
            return Result(
                answer_type='not_found',
                answer_text=f"I couldn't find relevant information. Best match similarity: {best_score:.2f}",
                reasoning="Content found but below confidence threshold.",
                confidence="none"
            )
        
        # Build answer from top results - organized by content type
        text_parts = []
        audio_parts = []
        table_parts = []
        image_parts = []
        
        for r in retrieved_results[:5]:
            content = r.get('content', r.get('page_content', '')).strip()
            content = ' '.join(content.split())  # Normalize whitespace
            metadata = r.get('metadata', {})
            element_type = metadata.get('element_type', metadata.get('chunk_type', 'text'))
            score = r.get('similarity_score', r.get('relevance_score', 0))
            
            if not content:
                continue
            
            # Truncate long content intelligently
            display_content = content
            if len(display_content) > 500:
                truncate_point = 500
                for sep in ['. ', '! ', '? ', '\n\n']:
                    last_sep = display_content[:truncate_point].rfind(sep)
                    if last_sep > truncate_point * 0.5:
                        truncate_point = last_sep + len(sep)
                        break
                display_content = display_content[:truncate_point] + "..."
            
            if element_type == 'audio':
                # Format audio with timestamp, speaker, and quoted transcript
                timestamp = metadata.get('timestamp_str', metadata.get('timestamp', ''))
                speaker = metadata.get('speaker', '')
                tone = metadata.get('tone', '')
                source_file = metadata.get('filename', 'Unknown audio')
                
                citation_label = f"[Audio: {source_file}"
                if timestamp:
                    citation_label += f" at {timestamp}"
                if speaker and speaker != 'Unknown':
                    citation_label += f", {speaker}"
                citation_label += "]"
                
                audio_entry = f'**{citation_label}**'
                if tone and tone != 'neutral':
                    audio_entry += f' *(tone: {tone})*'
                audio_entry += f':\n> "{display_content}"'
                
                audio_parts.append(audio_entry)
                
            elif element_type == 'table':
                source_file = metadata.get('filename', 'Unknown')
                page_num = metadata.get('page_number', '')
                rows = metadata.get('rows', 0)
                cols = metadata.get('columns', 0)
                
                table_entry = f'**[Table: {source_file}'
                if page_num:
                    table_entry += f", Page {page_num}"
                table_entry += f" ({rows} rows × {cols} columns)]**:\n"
                
                # Show analysis/summary if available
                analysis = metadata.get('analysis', '')
                if analysis:
                    # Take first 200 chars of analysis
                    analysis_summary = analysis[:200] + "..." if len(analysis) > 200 else analysis
                    table_entry += f"> {analysis_summary}"
                else:
                    table_entry += f"> {display_content[:300]}..."
                
                table_parts.append(table_entry)
                
            elif element_type == 'image':
                source_file = metadata.get('filename', 'Unknown')
                page_num = metadata.get('page_number', '')
                description = metadata.get('description', metadata.get('image_caption', ''))
                chart_type = metadata.get('chart_type', 'unknown')
                
                img_entry = f'**[Image: {source_file}'
                if page_num:
                    img_entry += f", Page {page_num}"
                if chart_type != 'unknown':
                    img_entry += f" - {chart_type} chart"
                img_entry += "]**:\n"
                
                if description:
                    desc_summary = description[:300] + "..." if len(description) > 300 else description
                    img_entry += f"> {desc_summary}"
                else:
                    img_entry += f"> {display_content[:300]}..."
                
                image_parts.append(img_entry)
                
            else:
                # Text content - standard format
                source_file = metadata.get('filename', 'Unknown')
                page_num = metadata.get('page_number', '')
                
                citation_label = f"[Source: {source_file}"
                if page_num:
                    citation_label += f", Page {page_num}"
                citation_label += "]"
                
                text_parts.append(f'**{citation_label}**:\n> {display_content}')
        
        # Combine all parts into the final answer
        answer_sections = []
        
        if text_parts:
            if len(text_parts) == 1:
                answer_sections.append(f"**From the document:**\n\n{text_parts[0]}")
            else:
                answer_sections.append("**From the documents:**\n\n" + "\n\n".join(text_parts))
        
        if audio_parts:
            if len(audio_parts) == 1:
                answer_sections.append(f"**From the audio recording:**\n\n{audio_parts[0]}")
            else:
                answer_sections.append("**From the audio recording:**\n\n" + "\n\n".join(audio_parts))
        
        if table_parts:
            answer_sections.append("**From tables in the documents:**\n\n" + "\n\n".join(table_parts))
        
        if image_parts:
            answer_sections.append("**From images in the documents:**\n\n" + "\n\n".join(image_parts))
        
        if answer_sections:
            answer = "\n\n---\n\n".join(answer_sections)
        else:
            answer = "Found relevant content but could not format it properly."
        
        if best_score >= 0.7:
            confidence = "high"
        elif best_score >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"
        
        return Result(
            answer_type='found',
            answer_text=answer,
            reasoning=f"Found {len(retrieved_results)} relevant passages with best score {best_score:.2f}",
            confidence=confidence
        )


# ============================================================================
# AUDIO PROCESSING
# ============================================================================

def process_audio_file(file_path: str) -> Dict[str, Any]:
    """
    Process audio file using Gemini API (preferred) or Whisper (fallback).
    
    Gemini is preferred as it provides speaker diarization, timestamps,
    and tone detection without needing local model downloads.
    """
    result = {
        'success': False,
        'text': '',
        'error': None
    }
    
    # Try Gemini first (no local model needed)
    try:
        import google.generativeai as genai
        import mimetypes
        
        api_key = os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        
        genai.configure(api_key=api_key)
        
        logger.info(f"Transcribing audio with Gemini: {file_path}")
        
        # Determine MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_type = mimetypes.guess_type(file_path)[0] or 'audio/mpeg'
        
        # Upload to Gemini
        audio_file = genai.upload_file(
            path=file_path,
            display_name=os.path.basename(file_path),
            mime_type=mime_type
        )
        
        # Transcribe with speaker diarization
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        prompt = """You are an expert audio transcription specialist. Provide a detailed transcription with speaker identification.

For each distinct speaker segment, provide:
1. The speaker identifier (Speaker 1, Speaker 2, etc.)
2. The timestamp (start time) in format [MM:SS]
3. The transcribed text for that segment
4. Speech characteristics: tone/emotion (neutral, happy, sad, angry, excited, professional, calm, etc.)
5. Confidence score for the transcription (0-1)

Format your response as a JSON array of segments:
[
  {
    "speaker": "Speaker 1",
    "timestamp": "[00:05]",
    "text": "Hello everyone, welcome to the presentation.",
    "tone": "neutral",
    "confidence": 0.92
  }
]

Return the result wrapped in: {"segments": [...], "summary": {"audio_quality": "...", "background_noise": "...", "language_detected": "...", "estimated_speakers": N}}
"""
        
        response = model.generate_content([prompt, audio_file])
        
        # Clean up uploaded file
        try:
            genai.delete_file(audio_file.name)
        except:
            pass
        
        # Parse the response
        transcript_text = response.text
        
        # Try to extract JSON
        import json
        segments = []
        full_text = ''
        
        try:
            json_match = re.search(r'\{.*\}', transcript_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if 'segments' in parsed:
                    for seg in parsed['segments']:
                        text = seg.get('text', '').strip()
                        speaker = seg.get('speaker', 'Unknown')
                        timestamp = seg.get('timestamp', '')
                        segments.append({
                            'text': text,
                            'speaker': speaker,
                            'timestamp': timestamp,
                            'timestamp_seconds': _parse_timestamp_to_seconds(timestamp),
                            'tone': seg.get('tone', 'neutral'),
                            'confidence': float(seg.get('confidence', 0.8))
                        })
                    full_text = ' '.join([s['text'] for s in segments])
        except Exception as parse_error:
            logger.warning(f"JSON parsing failed, using raw text: {parse_error}")
            full_text = transcript_text
        
        if not full_text:
            full_text = transcript_text
        
        result['success'] = True
        result['text'] = full_text
        result['segments'] = segments if segments else None
        
    except Exception as gemini_error:
        error_str = str(gemini_error)
        logger.warning(f"Gemini audio transcription failed: {gemini_error}")
        
        # Check if it's a quota error
        is_quota_error = '429' in error_str or 'quota' in error_str.lower() or 'RESOURCE_EXHAUSTED' in error_str
        
        # Fallback to Whisper if available
        if WHISPER_AVAILABLE:
            try:
                # Ensure ffmpeg is in PATH for whisper
                try:
                    import shutil as shutil_mod
                    from imageio_ffmpeg import get_ffmpeg_exe
                    ffmpeg_exe = get_ffmpeg_exe()
                    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
                    ffmpeg_standard = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
                    if not os.path.exists(ffmpeg_standard):
                        shutil_mod.copy2(ffmpeg_exe, ffmpeg_standard)
                    if ffmpeg_dir not in os.environ.get('PATH', ''):
                        os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                except Exception:
                    pass
                
                logger.info(f"Falling back to Whisper: {file_path}")
                model = whisper.load_model("base")
                transcription = model.transcribe(file_path)
                result['success'] = True
                result['text'] = transcription.get('text', '')
                result['segments'] = None
            except Exception as whisper_error:
                logger.error(f"Whisper transcription error: {whisper_error}")
                result['error'] = str(whisper_error)
        else:
            if is_quota_error:
                result['error'] = (
                    "Gemini API quota exceeded. Options:\n"
                    "1. Wait a few minutes and try again\n"
                    "2. Get a new API key at https://aistudio.google.com/app/apikey\n"
                    "3. Install Whisper for offline transcription: pip install openai-whisper"
                )
            else:
                result['error'] = f"Audio transcription failed: {gemini_error}. Install openai-whisper as fallback."
    
    return result


def _parse_timestamp_to_seconds(timestamp_str: str) -> float:
    """Convert timestamp string like 'MM:SS' or '[MM:SS]' to seconds."""
    try:
        # Remove brackets
        ts = timestamp_str.strip('[]').strip()
        parts = ts.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0.0
    except (ValueError, IndexError, AttributeError):
        return 0.0


# ============================================================================
# GLOBAL STATE
# ============================================================================

class RAGApplicationState:
    """Global state for the RAG application."""
    
    def __init__(self):
        self.embedding_manager = None
        self.vector_store = None
        self.document_processor = None
        self.answer_generator = None
        self.relevance_scorer = None  # Multimodal relevance scorer
        self.uploaded_files = {}
        self.is_initialized = False
        
    def initialize(self):
        """Initialize all components."""
        if self.is_initialized:
            return
            
        logger.info("Initializing RAG application...")
        
        # Initialize document processor
        self.document_processor = SimpleDocumentProcessor(
            chunk_size=app.config['CHUNK_SIZE'],
            chunk_overlap=app.config['CHUNK_OVERLAP']
        )
        
        # Initialize embedding manager - check for Gemini first
        embedding_provider = os.environ.get('EMBEDDING_PROVIDER', '').lower()
        
        # Track actual provider
        self.actual_embedding_provider = 'sentence-transformers'
        
        if embedding_provider == 'gemini':
            # Try to use Gemini Embedding 2
            try:
                from embedding_manager import EmbeddingManager
                
                gemini_dims = int(os.environ.get('GEMINI_EMBEDDING_DIMENSIONS', 768))
                
                self.embedding_manager = EmbeddingManager(
                    provider='gemini',
                    model_name='models/gemini-embedding-2-preview',
                    output_dimensions=gemini_dims,
                    task_type='retrieval_document'
                )
                self.actual_embedding_provider = 'gemini'
                logger.info(f"Using Gemini Embedding 2 with {gemini_dims} dimensions")
                
            except Exception as e:
                error_msg = str(e)
                # Check for Python version compatibility issue
                if "Metaclasses" in error_msg or "tp_new" in error_msg:
                    logger.warning(f"Gemini incompatible with Python 3.14: {error_msg}")
                    logger.info("Falling back to sentence-transformers (Gemini requires Python 3.11-3.13)")
                else:
                    logger.warning(f"Failed to initialize Gemini: {e}")
                    logger.info("Falling back to sentence-transformers")
                self.embedding_manager = SimpleEmbeddingManager('all-MiniLM-L6-v2')
                self.actual_embedding_provider = 'sentence-transformers'
        else:
            # Use default sentence-transformers
            self.embedding_manager = SimpleEmbeddingManager('all-MiniLM-L6-v2')
        
        # Initialize vector store
        self.vector_store = SimpleVectorStore(
            dimension=self.embedding_manager.get_embedding_dimension()
        )
        
        # Initialize answer generator
        self.answer_generator = SimpleAnswerGenerator(
            min_confidence=app.config['SIMILARITY_THRESHOLD']
        )
        
        # Initialize multimodal relevance scorer
        if RELEVANCE_SCORER_AVAILABLE:
            try:
                self.relevance_scorer = create_relevance_scorer(self.embedding_manager)
                logger.info("Multimodal relevance scorer initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize relevance scorer: {e}")
                self.relevance_scorer = None
        
        self.is_initialized = True
        logger.info("RAG application initialized successfully")


# Global state
app_state = RAGApplicationState()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_extension(filename: str) -> str:
    """Get file extension without dot."""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def generate_file_id() -> str:
    """Generate unique file ID."""
    return hashlib.md5(str(datetime.now().isoformat()).encode()).hexdigest()[:12]


def allowed_audio(filename: str) -> bool:
    """
    Check if the uploaded file is an allowed audio type.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        bool: True if allowed audio format, False otherwise
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config.get('ALLOWED_AUDIO_EXTENSIONS', AUDIO_EXTENSIONS)


def allowed_image(filename: str) -> bool:
    """
    Check if the uploaded file is an allowed image type.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        bool: True if allowed, False otherwise
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config.get('ALLOWED_IMAGE_EXTENSIONS', IMAGE_EXTENSIONS)


def validate_image_file(file, max_size: int = None) -> Dict[str, Any]:
    """
    Comprehensive validation for image uploads.
    
    Args:
        file: FileStorage object from Flask
        max_size: Maximum file size in bytes (defaults to MAX_IMAGE_SIZE)
        
    Returns:
        dict: {'valid': bool, 'error': str or None, 'size': int}
    """
    max_size = max_size or app.config.get('MAX_IMAGE_SIZE', 10 * 1024 * 1024)
    
    # Check filename
    if not file.filename or file.filename == '':
        return {'valid': False, 'error': 'No filename provided', 'size': 0}
    
    # Check extension
    if not allowed_image(file.filename):
        return {'valid': False, 'error': f'Image format not allowed. Supported: {", ".join(app.config.get("ALLOWED_IMAGE_EXTENSIONS", IMAGE_EXTENSIONS))}', 'size': 0}
    
    # Check file size (seek to end, then back to start)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > max_size:
        return {'valid': False, 'error': f'Image too large. Maximum size: {max_size // (1024*1024)}MB', 'size': size}
    
    if size == 0:
        return {'valid': False, 'error': 'Empty file uploaded', 'size': 0}
    
    return {'valid': True, 'error': None, 'size': size}


# ============================================================================
# FILE PROCESSING
# ============================================================================

def process_pdf_multimodal(file_path: str, file_id: str) -> Dict[str, Any]:
    """
    Process PDF using multimodal extraction to capture text, tables, and images.

    Args:
        file_path: Path to PDF file
        file_id: Unique file identifier

    Returns:
        Dict with processing results
    """
    result = {
        'success': False,
        'file_id': file_id,
        'file_name': os.path.basename(file_path),
        'file_type': 'pdf',
        'chunks_created': 0,
        'elements_extracted': {'text': 0, 'tables': 0, 'images': 0},
        'error': None
    }

    try:
        if not MULTIMODAL_AVAILABLE:
            result['error'] = "Multimodal processing not available. Install pymupdf, transformers, torch."
            logger.error("Multimodal dependencies not available")
            return result

        logger.info(f"Processing PDF with multimodal extraction: {file_path}")

        # Get extracted images directory
        extracted_images_dir = app.config.get('EXTRACTED_IMAGES_DIR')

        try:
            # Use the end-to-end chunk creation function
            chunks = create_chunks_from_pdf(
                pdf_path=file_path,
                file_id=file_id,
                filename=os.path.basename(file_path),
                output_image_dir=extracted_images_dir
            )
        except Exception as chunk_error:
            logger.error(f"Error creating chunks from PDF: {chunk_error}")
            import traceback
            traceback.print_exc()
            result['error'] = f"Failed to process PDF content: {str(chunk_error)}"
            return result

        if not chunks:
            result['error'] = "No content extracted from PDF"
            return result

        # Separate into LangChain documents for embedding
        documents = [chunk.to_langchain_document() for chunk in chunks]

        # Generate embeddings with error handling
        try:
            embeddings = app_state.embedding_manager.embed_documents(documents)
        except Exception as embed_error:
            logger.error(f"Error generating embeddings: {embed_error}")
            result['error'] = f"Failed to generate embeddings: {str(embed_error)}"
            return result

        metadatas = [doc.metadata for doc in documents]

        # Add to vector store
        app_state.vector_store.add_documents(documents, embeddings, metadatas)

        # Count element types
        element_counts = {'text': 0, 'table': 0, 'image': 0}
        for chunk in chunks:
            element_counts[chunk.element_type] += 1

        result['success'] = True
        result['chunks_created'] = len(chunks)
        result['elements_extracted'] = element_counts

        # Store file info
        app_state.uploaded_files[file_id] = {
            'file_path': file_path,
            'filename': os.path.basename(file_path),
            'file_type': '.pdf',
            'document_id': file_id,
            'chunks': len(chunks),
            'upload_time': datetime.now().isoformat(),
            'multimodal': True,
            'element_counts': element_counts
        }

        logger.info(f"PDF processed multimodal: {len(chunks)} chunks "
                    f"({element_counts['text']} text, {element_counts['table']} tables, "
                    f"{element_counts['image']} images)")

    except Exception as e:
        logger.error(f"Multimodal PDF processing error: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)

    return result


# ============================================================================
# UNIFIED GEMINI PROCESSOR INTEGRATION
# ============================================================================

def process_with_unified_processor(file_path: str, file_id: str) -> Dict[str, Any]:
    """
    Process files using the unified Gemini-powered processor.
    Supports PDF, DOCX, and audio files with deep analysis.
    """
    global unified_processor
    
    result = {
        'success': False,
        'file_id': file_id,
        'file_name': os.path.basename(file_path),
        'file_type': get_file_extension(file_path),
        'chunks_created': 0,
        'elements_extracted': {'text': 0, 'tables': 0, 'images': 0},
        'error': None
    }
    
    # Initialize processor if not already
    if unified_processor is None:
        try:
            api_key = os.environ.get('GOOGLE_API_KEY')
            unified_processor = create_processor(api_key)
            logger.info("Unified processor initialized")
        except Exception as e:
            result['error'] = f"Failed to initialize processor: {e}"
            return result
    
    try:
        logger.info(f"Processing with unified Gemini processor: {file_path}")
        
        # Get extracted images directory
        extracted_images_dir = app.config.get('EXTRACTED_IMAGES_DIR')
        
        # Process the file
        processed_doc = unified_processor.process_file(file_path, extract_images=True)
        
        if not processed_doc or not processed_doc.chunks:
            result['error'] = "No content extracted from file"
            return result
        
        # Save images to disk for display in sources - store mapping for metadata
        image_path_map = {}  # chunk_index -> image_path
        image_counter = 0
        for chunk_idx, chunk in enumerate(processed_doc.chunks):
            if chunk.chunk_type == 'image' and chunk.image_data:
                try:
                    import base64
                    # Decode base64 image data
                    img_bytes = base64.b64decode(chunk.image_data)
                    # Create unique filename using chunk_idx for consistency
                    image_counter += 1
                    img_filename = f"{chunk.document_id}_page{chunk.page_number or 1}_img{image_counter}.png"
                    img_path = os.path.join(extracted_images_dir, img_filename)
                    # Save to disk
                    with open(img_path, 'wb') as f:
                        f.write(img_bytes)
                    # Store the path for later use in metadata
                    image_path_map[chunk_idx] = img_filename
                    logger.info(f"Saved image: {img_filename}")
                except Exception as img_error:
                    logger.warning(f"Failed to save image: {img_error}")
        
        # Convert chunks to format for vector store
        # We need to create simple document objects
        class ChunkDoc:
            def __init__(self, content, meta):
                self.page_content = content
                self.metadata = meta
        
        documents = []
        metadatas = []
        
        for chunk in processed_doc.chunks:
            # Create metadata
            meta = {
                'document_id': chunk.document_id,
                'filename': chunk.source_file,
                'file_type': f'.{processed_doc.file_type}',
                'chunk_type': chunk.chunk_type,
                'chunk_index': len(documents),
                'page_number': chunk.page_number or 1
            }
            
            # Debug: log image chunks
            if chunk.chunk_type == 'image':
                logger.info(f"IMAGE CHUNK: page={chunk.page_number}, content_preview={chunk.content[:100]}...")
            
            # Add type-specific metadata
            if chunk.chunk_type == 'image':
                meta['element_type'] = 'image'
                meta['image_caption'] = chunk.metadata.get('description', '')
                meta['image_keywords'] = chunk.metadata.get('keywords', [])
                if chunk.image_data:
                    meta['has_image_data'] = True
                    # Use the saved image path from the map (key is current document count)
                    current_idx = len(documents)
                    if current_idx in image_path_map:
                        meta['image_path'] = os.path.join(extracted_images_dir, image_path_map[current_idx])
                    else:
                        # Fallback: generate filename
                        img_filename = f"{chunk.document_id}_page{chunk.page_number or 1}_img{current_idx+1}.png"
                        meta['image_path'] = os.path.join(extracted_images_dir, img_filename)
                    meta['element_id'] = f"{chunk.document_id}_page{chunk.page_number or 1}"
                # Enhanced image metadata
                meta['description'] = chunk.metadata.get('description', '')
                meta['chart_type'] = chunk.metadata.get('chart_type', 'unknown')
                meta['chart_title'] = chunk.metadata.get('chart_title', '')
                meta['chart_caption'] = chunk.metadata.get('chart_caption', '')
                meta['data_points'] = chunk.metadata.get('data_points', [])
                meta['text_blocks'] = chunk.metadata.get('text_blocks', [])
                meta['trends'] = chunk.metadata.get('trends', [])
                meta['axes_info'] = chunk.metadata.get('axes_info', {})
                meta['legends_info'] = chunk.metadata.get('legends_info', [])
                meta['statistics_visible'] = chunk.metadata.get('statistics_visible', [])
                meta['document_type'] = chunk.metadata.get('document_type', 'unknown')
                meta['subject_area'] = chunk.metadata.get('subject_area', 'unknown')
                meta['likely_purpose'] = chunk.metadata.get('likely_purpose', 'unknown')
                meta['objects_detected'] = chunk.metadata.get('objects_detected', [])
                meta['confidence_scores'] = chunk.metadata.get('confidence_scores', {})
                meta['has_chart_data'] = chunk.metadata.get('has_chart_data', False)
                meta['has_text_content'] = chunk.metadata.get('has_text_content', False)
                meta['has_objects'] = chunk.metadata.get('has_objects', False)
            elif chunk.chunk_type == 'table':
                meta['element_type'] = 'table'
                meta['table_data'] = chunk.table_data
                # Enhanced table metadata
                meta['analysis'] = chunk.metadata.get('analysis', '')
                meta['rows'] = chunk.metadata.get('rows', 0)
                meta['columns'] = chunk.metadata.get('columns', 0)
                meta['table_structure'] = chunk.metadata.get('table_structure', {})
                meta['column_details'] = chunk.metadata.get('column_details', [])
                meta['relationships'] = chunk.metadata.get('relationships', [])
                meta['patterns_insights'] = chunk.metadata.get('patterns_insights', [])
                meta['data_quality'] = chunk.metadata.get('data_quality', {})
                meta['suggested_visualizations'] = chunk.metadata.get('suggested_visualizations', [])
                meta['potential_use_cases'] = chunk.metadata.get('potential_use_cases', [])
                meta['confidence_scores'] = chunk.metadata.get('confidence_scores', {})
                meta['has_numeric_data'] = chunk.metadata.get('has_numeric_data', False)
                meta['has_date_data'] = chunk.metadata.get('has_date_data', False)
                meta['key_columns'] = chunk.metadata.get('key_columns', [])
                meta['header_row_present'] = chunk.metadata.get('header_row_present', False)
            elif chunk.chunk_type == 'audio':
                meta['element_type'] = 'audio'
                meta['timestamp'] = chunk.timestamp
                meta['timestamp_str'] = chunk.metadata.get('timestamp_str', '')
                # Enhanced audio metadata
                meta['speaker'] = chunk.metadata.get('speaker', 'Unknown')
                meta['tone'] = chunk.metadata.get('tone', 'neutral')
                meta['confidence'] = chunk.metadata.get('confidence', 0.8)
                meta['word_count'] = chunk.metadata.get('word_count', 0)
                meta['is_speaker_change'] = chunk.metadata.get('is_speaker_change', False)
                # Full transcript metadata
                if chunk.metadata.get('is_full_transcript'):
                    meta['is_full_transcript'] = True
                    meta['unique_speakers'] = chunk.metadata.get('unique_speakers', [])
                    meta['diarization_success'] = chunk.metadata.get('diarization_success', False)
                    meta['audio_quality'] = chunk.metadata.get('audio_quality', 'unknown')
                    meta['background_noise'] = chunk.metadata.get('background_noise', 'none detected')
                    meta['language_detected'] = chunk.metadata.get('language_detected', 'unknown')
                    meta['estimated_speakers'] = chunk.metadata.get('estimated_speakers', 1)
                    meta['speech_rate_wpm'] = chunk.metadata.get('speech_rate_wpm', 0.0)
            
            # Add to lists - use chunk.content
            documents.append(ChunkDoc(chunk.content, meta))
            metadatas.append(meta)
        
        # Generate embeddings using the unified processor's embeddings
        if processed_doc.chunks and processed_doc.chunks[0].embedding:
            # Use pre-computed embeddings from the processor
            embeddings = [chunk.embedding for chunk in processed_doc.chunks]
        else:
            # Fallback: generate embeddings using app's embedding manager
            logger.info("Using app embedding manager for embeddings")
            text_contents = [chunk.content for chunk in processed_doc.chunks]
            embeddings = app_state.embedding_manager.embed_documents(text_contents)
        
        # Add to vector store
        app_state.vector_store.add_documents(documents, embeddings, metadatas)
        
        # Debug: log document counts by type
        type_counts = {'text': 0, 'table': 0, 'image': 0, 'audio': 0}
        for m in metadatas:
            ct = m.get('chunk_type', 'text')
            if ct in type_counts:
                type_counts[ct] += 1
        logger.info(f"Documents added to vector store: {type_counts}")
        
        # Count elements
        element_counts = {'text': 0, 'table': 0, 'image': 0, 'audio': 0}
        for chunk in processed_doc.chunks:
            if chunk.chunk_type == 'text':
                element_counts['text'] += 1
            elif chunk.chunk_type in element_counts:
                element_counts[chunk.chunk_type] += 1
        
        result['success'] = True
        result['chunks_created'] = len(processed_doc.chunks)
        result['elements_extracted'] = element_counts
        
        # Store file info
        app_state.uploaded_files[file_id] = {
            'file_path': file_path,
            'filename': os.path.basename(file_path),
            'file_type': f'.{processed_doc.file_type}',
            'document_id': file_id,
            'chunks': len(processed_doc.chunks),
            'upload_time': datetime.now().isoformat(),
            'multimodal': True,
            'element_counts': element_counts,
            'gemini_processed': True
        }
        
        logger.info(f"Unified processor: {len(processed_doc.chunks)} chunks "
                   f"({element_counts['text']} text, {element_counts['table']} tables, "
                   f"{element_counts['image']} images, {element_counts['audio']} audio)")
        
    except Exception as e:
        logger.error(f"Unified processor error: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


def process_uploaded_file(file_path: str, file_id: str) -> Dict[str, Any]:
    """Process an uploaded file based on its type."""
    result = {
        'success': False,
        'file_id': file_id,
        'file_name': os.path.basename(file_path),
        'file_type': get_file_extension(file_path),
        'chunks_created': 0,
        'error': None
    }
    
    try:
        file_ext = get_file_extension(file_path)
        filename = os.path.basename(file_path)
        
        documents = []
        
        # Use multimodal chunker (original working path) for PDFs
        if file_ext == 'pdf':
            # Use multimodal processing if available and enabled, otherwise fallback to basic
            if MULTIMODAL_AVAILABLE and app.config.get('USE_MULTIMODAL_PDF', True):
                try:
                    logger.info(f"Processing PDF with multimodal extraction: {file_path}")
                    return process_pdf_multimodal(file_path, file_id)
                except Exception as multimodal_error:
                    logger.error(f"Multimodal processing failed, falling back to basic: {multimodal_error}")
                    logger.info(f"Processing PDF with basic loader: {file_path}")
                    documents = app_state.document_processor.load_document(file_path)
            else:
                logger.info(f"Processing PDF with basic loader: {file_path}")
                documents = app_state.document_processor.load_document(file_path)
                
        elif file_ext == 'docx':
            # Use unified processor for DOCX if available
            if UNIFIED_PROCESSOR_AVAILABLE:
                try:
                    logger.info(f"Processing DOCX with unified Gemini processor: {file_path}")
                    return process_with_unified_processor(file_path, file_id)
                except Exception as unified_error:
                    logger.error(f"Unified processor failed, falling back to basic: {unified_error}")
            
            logger.info(f"Processing DOCX: {file_path}")
            documents = app_state.document_processor.load_document(file_path)
            
        elif file_ext == 'txt':
            logger.info(f"Processing TXT: {file_path}")
            documents = app_state.document_processor.load_document(file_path)
            
        elif file_ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac', 'aac', 'wma', 'aiff', 'opus', 'webm', 'amr', '3gp', 'midi', 'mid', 'ra', 'ram', 'mp2', 'ac3', 'mp4', 'm4b', 'm4p', 'oga']:
            logger.info(f"Processing audio: {file_path}")
            audio_result = process_audio_file(file_path)
            
            if audio_result['success']:
                # Create a document from transcribed text
                class TextDoc:
                    def __init__(self, text, metadata):
                        self.page_content = text
                        self.metadata = metadata
                
                doc = TextDoc(
                    text=audio_result['text'],
                    metadata={
                        'source': file_path,
                        'filename': filename,
                        'file_type': f'.{file_ext}',
                        'document_id': file_id,
                        'source_type': 'audio',
                        'page_number': 1
                    }
                )
                documents = [doc]
            else:
                result['error'] = audio_result['error']
                return result
        else:
            result['error'] = f"Unsupported file type: {file_ext}"
            return result
        
        # Chunk documents
        if documents:
            logger.info(f"Document count: {len(documents)}")
            logger.info(f"First doc type: {type(documents[0])}")
            
            try:
                chunks = app_state.document_processor.chunk_documents(documents)
                logger.info(f"Chunk count after chunking: {len(chunks)}")
            except Exception as chunk_error:
                logger.error(f"Chunking error: {chunk_error}")
                import traceback
                traceback.print_exc()
                result['error'] = f"Chunking error: {str(chunk_error)}"
                return result
            
            # Add metadata to chunks
            for i, chunk in enumerate(chunks):
                if not hasattr(chunk, 'metadata') or not chunk.metadata:
                    chunk.metadata = {}
                chunk.metadata['chunk_index'] = i
                chunk.metadata['document_id'] = file_id
                chunk.metadata['filename'] = filename
            
            # Generate embeddings with timeout protection
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            logger.info(f"First chunk type: {type(chunks[0]) if chunks else 'None'}")
            
            try:
                # Convert chunks to text strings if needed
                text_contents = []
                for chunk in chunks:
                    if hasattr(chunk, 'page_content'):
                        text_contents.append(chunk.page_content)
                    else:
                        text_contents.append(str(chunk))
                
                logger.info(f"Text contents count: {len(text_contents)}, first length: {len(text_contents[0]) if text_contents else 0}")
                embeddings_result = app_state.embedding_manager.embed_documents(text_contents)
                logger.info(f"Embedding result type: {type(embeddings_result)}, count: {len(embeddings_result) if embeddings_result else 0}")
            except Exception as emb_error:
                logger.error(f"Embedding error: {emb_error}")
                import traceback
                traceback.print_exc()
                result['error'] = f"Embedding error: {str(emb_error)}"
                return result
            
            if embeddings_result is None:
                # Timeout or error - try with fewer chunks as fallback
                logger.warning("Embedding generation timed out, trying with first chunk only")
                try:
                    # Try with just the first chunk as emergency fallback
                    single_chunk = chunks[:1]
                    # Convert to text first
                    single_text = [single_chunk[0].page_content] if hasattr(single_chunk[0], 'page_content') else [str(single_chunk[0])]
                    embeddings_result = app_state.embedding_manager.embed_documents(single_text)
                    chunks = single_chunk
                    logger.info("Using emergency fallback: single chunk embedding")
                except Exception as fallback_error:
                    logger.error(f"Fallback embedding also failed: {fallback_error}")
                    result['error'] = "Failed to generate embeddings - operation timed out. Please try a smaller file."
                    return result
            
            metadatas = [c.metadata for c in chunks]
            
            # Add to vector store with timeout
            logger.info("Adding documents to vector store...")
            store_result = run_with_timeout(
                app_state.vector_store.add_documents,
                args=(chunks, embeddings_result, metadatas),
                timeout_seconds=60,
                default=False
            )
            
            if store_result is False:
                logger.warning("Vector store add timed out, but continuing anyway")
            
            result['success'] = True
            result['chunks_created'] = len(chunks)
            
            # Store file info
            app_state.uploaded_files[file_id] = {
                'file_path': file_path,
                'filename': filename,
                'file_type': f'.{file_ext}',
                'document_id': file_id,
                'chunks': len(chunks),
                'upload_time': datetime.now().isoformat()
            }
            
            logger.info(f"File processed: {filename}, {len(chunks)} chunks")
        else:
            result['error'] = "No content extracted from file"
            
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


def process_image_file(file_path: str, file_id: str) -> Dict[str, Any]:
    """
    Process an uploaded image file using BLIP-2 for captioning and Tesseract for OCR.
    
    Args:
        file_path: Path to the uploaded image
        file_id: Unique identifier for the file
        
    Returns:
        dict: Processing result with success status and details including caption and OCR text
    """
    result = {
        'success': False,
        'file_id': file_id,
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_type': 'image',
        'processing_mode': 'multimodal',
        'description': None,
        'caption': None,
        'ocr_text': None,
        'has_text': False,
        'error': None
    }
    
    try:
        # Read image file as bytes
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        if not image_bytes:
            result['error'] = 'Empty image file'
            logger.error(f"Empty image file: {file_path}")
            return result
        
        # Try to use ImageAnalyzer (BLIP-2 + Tesseract) as primary
        logger.info(f"Processing image with BLIP-2 and Tesseract: {file_path}")
        
        try:
            # Create image analyzer
            analyzer = create_image_analyzer()
            
            # Perform comprehensive analysis
            analysis = analyzer.analyze(image_bytes)
            
            # Build comprehensive description
            description_parts = []
            
            if analysis.get('caption'):
                description_parts.append(f"**Image Description:** {analysis['caption']}")
                result['caption'] = analysis['caption']
            
            if analysis.get('ocr_text'):
                description_parts.append(f"**Text in Image:**\n{analysis['ocr_text']}")
                result['ocr_text'] = analysis['ocr_text']
                result['has_text'] = True
            
            if description_parts:
                result['description'] = "\n\n".join(description_parts)
                result['success'] = True
                result['processing_mode'] = 'blip2_tesseract'
                logger.info(f"Image analyzed successfully with BLIP-2 and Tesseract: {file_path}")
            else:
                # No caption or OCR text extracted
                result['error'] = 'No content could be extracted from the image. The image may be corrupted or unsupported.'
                logger.warning(f"No content extracted from image: {file_path}")
                
        except Exception as analyzer_error:
            logger.warning(f"ImageAnalyzer failed, falling back to Nemotron: {analyzer_error}")
            
            # Fallback to Nemotron if ImageAnalyzer fails
            if NEMOTRON_AVAILABLE:
                try:
                    logger.info(f"Using Nemotron fallback for: {file_path}")
                    nemotron_description = GetDescriptionFromLLM(file_path, max_retries=2, timeout=90)
                    
                    if nemotron_description and not ('failed' in nemotron_description.lower() or 'error' in nemotron_description.lower() or 'timed out' in nemotron_description.lower()):
                        result['description'] = nemotron_description
                        result['success'] = True
                        result['processing_mode'] = 'nemotron_fallback'
                        logger.info(f"Image processed with Nemotron fallback: {file_path}")
                    else:
                        result['error'] = f"All vision methods failed. Last attempt returned: {nemotron_description}"
                        logger.error(f"Nemotron also failed for: {file_path}")
                except Exception as nemotron_error:
                    result['error'] = f"Both BLIP-2/Tesseract and Nemotron failed. Primary error: {analyzer_error}, Fallback error: {nemotron_error}"
                    logger.error(f"All vision methods failed for {file_path}")
            else:
                result['error'] = f"Image analysis failed and Nemotron fallback not available. Error: {analyzer_error}"
                logger.error(f"No fallback available for {file_path}")
        
    except FileNotFoundError as e:
        result['error'] = f'Image file not found: {str(e)}'
        logger.error(f"Image file not found: {file_path}")
    except ValueError as e:
        result['error'] = f'Invalid image format: {str(e)}'
        logger.error(f"Invalid image format: {file_path}")
    except Exception as e:
        result['error'] = f'Processing failed: {str(e)}'
        logger.error(f"Image processing error: {e}")
        import traceback
        traceback.print_exc()
    
    return result


# ============================================================================
# QUERY PROCESSING
# ============================================================================

def retrieve_and_answer(query: str, max_results: int = 5, course_id: str = None) -> Dict[str, Any]:
    """Retrieve relevant documents and generate answer with citations using multimodal re-ranking.
    
    Args:
        query: The user's question
        max_results: Maximum number of documents to return
        course_id: Optional course ID to filter documents (for data leakage prevention)
    """
    result = {
        'success': False,
        'answer': '',
        'citations': [],
        'error': None
    }
    
    try:
        # Embed the query
        query_embedding = app_state.embedding_manager.embed_query(query)
        
        # Search vector store (get more results for re-ranking)
        initial_k = max(max_results * 3, 20)  # Get 3x for re-ranking
        search_results = app_state.vector_store.similarity_search(
            query_embedding=query_embedding,
            k=initial_k * 3  # Get more to filter from
        )
        
        # =====================================================
        # COURSE SCOPING - Data Leakage Prevention
        # =====================================================
        # If course_id is provided, filter documents to only include those
        # from the enrolled course. This prevents students from accessing
        # materials from courses they're not enrolled in.
        if course_id:
            filtered_results = []
            for doc in search_results:
                doc_course_id = doc.metadata.get('course_id') if hasattr(doc, 'metadata') else None
                # Include if no course_id set (global docs) or matches the requested course
                if doc_course_id is None or doc_course_id == course_id:
                    filtered_results.append(doc)
            
            search_results = filtered_results
            logger.info(f"Course-scoped search: {len(search_results)} / {len(filtered_results)} docs for course {course_id}")
        
        # Debug: log search result types
        result_types = {'text': 0, 'table': 0, 'image': 0, 'audio': 0}
        for doc in search_results:
            et = doc.metadata.get('element_type', doc.metadata.get('chunk_type', 'text'))
            if et in result_types:
                result_types[et] += 1
        logger.info(f"Search results types: {result_types}")
        
        # Force-include image results if any exist in vector store
        all_docs = app_state.vector_store.documents
        image_docs = [d for d in all_docs if d.metadata.get('element_type') == 'image' or d.metadata.get('chunk_type') == 'image']
        
        logger.info(f"Total docs in store: {len(all_docs)}, Image docs: {len(image_docs)}")
        
        if image_docs:
            # Get all non-image results
            non_image_results = [d for d in search_results if d.metadata.get('element_type') != 'image' and d.metadata.get('chunk_type') != 'image']
            
            # Replace some text results with images if no images in results
            if not any(d.metadata.get('element_type') == 'image' for d in search_results):
                logger.info(f"Adding {min(len(image_docs), 2)} image results to search results")
                # Replace lowest-scoring non-image with images
                for img_doc in image_docs[:2]:  # Add up to 2 images
                    # Give it a reasonable score
                    img_doc.metadata['similarity_score'] = 0.5
                    img_doc.metadata['relevance_score'] = 0.5
                    search_results.append(img_doc)
        
        if not search_results:
            result['answer'] = "No documents found. Please upload documents first."
            result['success'] = True
            return result
        
        # Apply multimodal re-ranking if available
        if app_state.relevance_scorer and len(search_results) > 1:
            try:
                reranked = app_state.relevance_scorer.rerank_results(
                    query=query,
                    initial_results=search_results,
                    top_k=max_results
                )
                # Convert back to list of docs with updated scores
                search_results = []
                for chunk, score, breakdown in reranked:
                    if hasattr(chunk, 'metadata'):
                        chunk.metadata['relevance_score'] = score
                        chunk.metadata['relevance_breakdown'] = breakdown
                        # Keep the original similarity score too
                        if 'similarity_score' not in chunk.metadata:
                            chunk.metadata['similarity_score'] = score
                    search_results.append(chunk)
                logger.info(f"Re-ranked {len(reranked)} results using multimodal scorer")
            except Exception as e:
                logger.warning(f"Re-ranking failed, using original results: {e}")
                search_results = search_results[:max_results]
        else:
            search_results = search_results[:max_results]
        
        # Prepare retrieved results
        retrieved_data = []
        for doc in search_results:
            score = doc.metadata.get('similarity_score', 0) if hasattr(doc, 'metadata') else 0
            relevance_score = doc.metadata.get('relevance_score', score) if hasattr(doc, 'metadata') else score
            retrieved_data.append({
                'content': doc.page_content if hasattr(doc, 'page_content') else str(doc),
                'metadata': doc.metadata if hasattr(doc, 'metadata') else {},
                'similarity_score': score,
                'relevance_score': relevance_score
            })
        
        # Generate answer
        generated_answer = app_state.answer_generator.generate(
            query=query,
            retrieved_results=retrieved_data,
            total_documents=len(app_state.uploaded_files)
        )
        
        # Build enhanced citations with multimodal support
        citations = []
        for doc in search_results:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            page_num = metadata.get('page_number', 'N/A')
            element_type = metadata.get('element_type', metadata.get('chunk_type', 'text'))
            
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            verbatim = content[:300]
            if len(content) > 300:
                verbatim += "..."
            
            # Build base citation
            citation = {
                'source_file': metadata.get('filename', 'Unknown'),
                'page_number': page_num,
                'chunk_index': metadata.get('chunk_index', 0),
                'similarity_score': metadata.get('similarity_score', 0),
                'relevance_score': metadata.get('relevance_score', metadata.get('similarity_score', 0)),
                'verbatim': verbatim,
                'full_text': content,
                'source_type': element_type,
                'location': f"Page {page_num}, {element_type.title()}"
            }
            
            # Add relevance breakdown if available
            if 'relevance_breakdown' in metadata:
                citation['relevance_breakdown'] = metadata['relevance_breakdown']
            
            # Add type-specific fields for tables
            if element_type == 'table':
                citation['is_table'] = True
                citation['markdown_table'] = content
                citation['location'] = f"Page {page_num}, Table"
                # Enhanced table metadata
                if 'table_structure' in metadata:
                    citation['table_structure'] = metadata['table_structure']
                if 'column_details' in metadata:
                    citation['column_details'] = metadata['column_details']
                if 'patterns_insights' in metadata:
                    citation['patterns_insights'] = metadata['patterns_insights']
                if 'rows' in metadata:
                    citation['table_rows'] = metadata['rows']
                if 'columns' in metadata:
                    citation['table_columns'] = metadata['columns']
            
            # Add type-specific fields for images
            elif element_type == 'image':
                citation['is_image'] = True
                citation['image_caption'] = metadata.get('image_caption', metadata.get('description', ''))
                citation['ocr_text'] = metadata.get('ocr_text', '')
                citation['has_text'] = metadata.get('has_text', metadata.get('has_text_content', False))
                # Enhanced image metadata
                if 'chart_type' in metadata:
                    citation['chart_type'] = metadata['chart_type']
                if 'data_points' in metadata:
                    citation['data_points'] = metadata['data_points']
                if 'trends' in metadata:
                    citation['trends'] = metadata['trends']
                if 'chart_title' in metadata:
                    citation['chart_title'] = metadata['chart_title']
                if 'subject_area' in metadata:
                    citation['subject_area'] = metadata['subject_area']
                
                # If image was saved, provide URL
                if 'image_path' in metadata:
                    img_filename = os.path.basename(metadata['image_path'])
                    citation['image_url'] = f"/static/extracted_images/{img_filename}"
                elif 'element_id' in metadata:
                    img_filename = f"{metadata['element_id']}.png"
                    citation['image_url'] = f"/static/extracted_images/{img_filename}"
            
            # Add type-specific fields for audio
            elif element_type == 'audio':
                citation['is_audio'] = True
                citation['timestamp'] = metadata.get('timestamp_str', metadata.get('timestamp', ''))
                citation['timestamp_seconds'] = metadata.get('timestamp', 0)
                # Enhanced audio metadata
                if 'speaker' in metadata:
                    citation['speaker'] = metadata['speaker']
                if 'tone' in metadata:
                    citation['tone'] = metadata['tone']
                if 'confidence' in metadata:
                    citation['transcription_confidence'] = metadata['confidence']
                if 'is_speaker_change' in metadata:
                    citation['is_speaker_change'] = metadata['is_speaker_change']
                if 'audio_quality' in metadata:
                    citation['audio_quality'] = metadata['audio_quality']
            
            citations.append(citation)
        
        # Build answer text (citations are sent separately for frontend rendering)
        answer_text = generated_answer.answer_text
        
        result['success'] = True
        result['answer'] = answer_text
        result['citations'] = citations
        result['answer_type'] = generated_answer.answer_type
        result['confidence'] = generated_answer.confidence
        result['reranking_applied'] = app_state.relevance_scorer is not None
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


# ============================================================================
# AUTHENTICATION SYSTEM (Supabase-backed via Node.js API)
# ============================================================================

# Node.js API URL (runs on port 3000)
NODE_API_URL = "http://localhost:3000"


class User:
    """Simple user model for authentication."""
    
    def __init__(self, user_id: str, email: str, full_name: str, password_hash: str, role: str):
        self.user_id = user_id
        self.email = email
        self.full_name = full_name
        self.password_hash = password_hash
        self.role = role  # 'student' or 'teacher'
        self.created_at = datetime.now()
        self.last_login = None
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class AuthSession:
    """Session manager that stores users in Supabase via Node.js API."""
    
    def __init__(self):
        self.sessions = {}  # token -> user_id
        # Cache users locally for faster auth
        self.users_cache = {}  # user_id -> User
    
    def create_user(self, email: str, full_name: str, password: str, role: str) -> tuple:
        """Create a new user in Supabase. Returns (user, error)."""
        try:
            # First, check if user exists in Supabase
            response = requests.get(f"{NODE_API_URL}/users", timeout=5)
            if response.status_code == 200:
                existing_users = response.json()
                for u in existing_users:
                    if u.get('email', '').lower() == email.lower():
                        return None, 'Email already registered'
            
            # Create user in Supabase
            user_data = {
                'email': email.lower().strip(),
                'password': password,  # Will be hashed in Flask for now
                'full_name': full_name.strip(),
                'role': role
            }
            
            response = requests.post(
                f"{NODE_API_URL}/auth/register",
                json=user_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                user = User(
                    user_id=str(data.get('id')),
                    email=email.lower(),
                    full_name=full_name.strip(),
                    password_hash=self._hash_password(password),
                    role=role
                )
                self.users_cache[user.user_id] = user
                logger.info(f"User created in Supabase: {email} ({role})")
                return user, None
            else:
                return None, f"Failed to create user: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return None, "Database server not running. Please start the Node.js server."
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None, str(e)
    
    def authenticate(self, email: str, password: str) -> tuple:
        """Authenticate user from Supabase. Returns (user, error)."""
        try:
            # Get user from Supabase
            response = requests.get(f"{NODE_API_URL}/users", timeout=5)
            
            if response.status_code != 200:
                return None, "Database connection error"
            
            users = response.json()
            password_hash = self._hash_password(password)
            
            # Find user with matching email and password
            for u in users:
                if u.get('email', '').lower() == email.lower():
                    stored_hash = u.get('password_hash', '')
                    if stored_hash == password_hash:
                        user = User(
                            user_id=str(u.get('id')),
                            email=u.get('email', ''),
                            full_name=u.get('full_name', ''),
                            password_hash=stored_hash,
                            role=u.get('role', 'student')
                        )
                        user.last_login = datetime.now()
                        self.users_cache[user.user_id] = user
                        logger.info(f"User authenticated: {email} ({user.role})")
                        return user, None
                    else:
                        return None, 'Invalid email or password'
            
            return None, 'Invalid email or password'
            
        except requests.exceptions.ConnectionError:
            return None, "Database server not running. Please start the Node.js server."
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return None, "Authentication failed"
    
    def get_user_by_id(self, user_id: str):
        """Get user from cache or database."""
        if user_id in self.users_cache:
            return self.users_cache[user_id]
        
        try:
            response = requests.get(f"{NODE_API_URL}/users/{user_id}", timeout=5)
            if response.status_code == 200:
                u = response.json()
                user = User(
                    user_id=str(u.get('id')),
                    email=u.get('email', ''),
                    full_name=u.get('full_name', ''),
                    password_hash=u.get('password_hash', ''),
                    role=u.get('role', 'student')
                )
                self.users_cache[user.user_id] = user
                return user
        except:
            pass
        return None
    
    def get_session(self, token: str):
        """Get user from session token."""
        user_id = self.sessions.get(token)
        if not user_id:
            return None
        return self.get_user_by_id(user_id)
    
    def create_session(self, user: User) -> str:
        """Create session token for user."""
        token = secrets.token_hex(32)
        self.sessions[token] = user.user_id
        return token
    
    def delete_session(self, token: str) -> bool:
        """Delete session (logout)."""
        if token in self.sessions:
            del self.sessions[token]
            return True
        return False
    
    def _hash_password(self, password: str) -> str:
        """Simple SHA256 password hashing (matches Node.js)."""
        return hashlib.sha256(password.encode()).hexdigest()


# Initialize auth system
auth_session = AuthSession()

# Seed some test users for development
def _seed_test_users():
    """Create test users for development."""
    # Teacher account
    auth_session.create_user(
        'teacher@cpts421.edu',
        'Dr. Instructor',
        'teacher123',
        'teacher'
    )
    # Student account
    auth_session.create_user(
        'student@cpts421.edu', 
        'Student User',
        'student123',
        'student'
    )
    logger.info("Test users seeded: teacher@cpts421.edu / teacher123, student@cpts421.edu / student123")

_seed_test_users()


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/login')
def login():
    """Render the login page."""
    return render_template('login.html')


# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.route('/auth/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Expected JSON: { full_name, email, password, role }
    Returns: { success: true/false, user?: {...}, error?: "..." }
    """
    try:
        data = request.get_json()
        
        full_name = data.get('full_name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        role = data.get('role', 'student')
        
        # Validate
        if not full_name or not email or not password:
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        # Create user
        user, error = auth_session.create_user(email, full_name, password, role)
        
        if error:
            return jsonify({'success': False, 'error': error}), 400
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/auth/login', methods=['POST'])
def login_auth():
    """
    Authenticate user and create session.
    
    Expected JSON: { email, password }
    Returns: { success: true/false, user?: {...}, redirect?: "/..." }
    """
    try:
        data = request.get_json()
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400
        
        # Authenticate
        user, error = auth_session.authenticate(email, password)
        
        if error:
            return jsonify({'success': False, 'error': error}), 401
        
        # Create session token
        token = auth_session.create_session(user)
        
        # Determine redirect based on role
        if user.role == 'teacher':
            redirect_url = '/instructor/dashboard'
        else:
            redirect_url = '/student/home'
        
        # Set session cookie
        response = jsonify({
            'success': True,
            'user': user.to_dict(),
            'redirect': redirect_url
        })
        response.set_cookie('session_token', token, httponly=True, samesite='Lax', max_age=86400)
        
        return response
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user."""
    try:
        # Get session token from cookie
        token = request.cookies.get('session_token')
        
        if not token:
            return jsonify({'authenticated': False}), 401
        
        user = auth_session.get_session(token)
        
        if not user:
            return jsonify({'authenticated': False}), 401
        
        return jsonify({
            'authenticated': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Session check error: {e}")
        return jsonify({'authenticated': False}), 401


@app.route('/auth/logout', methods=['POST', 'GET'])
def logout_auth():
    """Logout current user."""
    try:
        token = request.cookies.get('session_token')
        
        if token:
            auth_session.delete_session(token)
        
        response = jsonify({'success': True, 'redirect': '/login'})
        response.set_cookie('session_token', '', expires=0)
        
        return response
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# INSTRUCTOR COURSE ENDPOINTS
# ============================================================================

@app.route('/api/courses', methods=['GET'])
def get_courses():
    """Get all courses (for instructor dashboard)."""
    try:
        # Get current user from session
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Fetch courses from Supabase via Express API
        try:
            response = requests.get(f"{NODE_API_URL}/course", timeout=10)
            if response.status_code == 200:
                courses = response.json()
                return jsonify({'courses': courses})
            else:
                logger.error(f"Failed to fetch courses: {response.text}")
                return jsonify({'courses': []})
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'courses': []})
            
    except Exception as e:
        logger.error(f"Get courses error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses', methods=['POST'])
def create_course():
    """Create a new course (instructor only)."""
    try:
        # Get current user from session
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        name = data.get('name', '').strip()
        code = data.get('code', '').strip().upper()
        
        if not name or not code:
            return jsonify({'error': 'Name and code are required'}), 400
        
        # Create course in Supabase via Express API
        try:
            response = requests.post(
                f"{NODE_API_URL}/course",
                json={
                    'name': name,
                    'code': code,
                    'description': '',
                    'teacher_id': int(user.user_id) if user.user_id.isdigit() else 1
                },
                timeout=10
            )
            
            if response.status_code == 201:
                course = response.json()
                logger.info(f"Course created: {name} ({code}) by teacher {user.email}")
                return jsonify({'success': True, 'course': course}), 201
            else:
                logger.error(f"Failed to create course in database: {response.text}")
                return jsonify({'error': 'Failed to create course in database'}), 500
                
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'error': 'Database connection error'}), 500
            
    except Exception as e:
        logger.error(f"Create course error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>', methods=['GET'])
def get_course(course_id):
    """Get a specific course."""
    try:
        # Get current user from session
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Fetch course from Supabase via Express API
        try:
            response = requests.get(f"{NODE_API_URL}/course/{course_id}", timeout=10)
            if response.status_code == 200:
                return jsonify({'course': response.json()})
            else:
                return jsonify({'error': 'Course not found'}), 404
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'error': 'Database connection error'}), 500
            
    except Exception as e:
        logger.error(f"Get course error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>', methods=['PUT'])
def update_course(course_id):
    """Update a course (name, code, etc)."""
    try:
        # Get current user from session
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Update course in Supabase via Express API
        try:
            response = requests.put(
                f"{NODE_API_URL}/course/{course_id}",
                json=data,
                timeout=10
            )
            if response.status_code == 200:
                return jsonify({'success': True, 'course': response.json()})
            else:
                return jsonify({'error': 'Course not found'}), 404
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'error': 'Database connection error'}), 500
        
    except Exception as e:
        logger.error(f"Update course error: {e}")
        return jsonify({'error': str(e)}), 500
        for course in courses:
            if course['id'] == course_id:
                if 'name' in data:
                    course['name'] = data['name']
                if 'code' in data:
                    course['code'] = data['code'].upper()
                course['updated_at'] = datetime.now().isoformat()
                return jsonify({'success': True, 'course': course})
        
        return jsonify({'error': 'Course not found'}), 404
    except Exception as e:
        logger.error(f"Update course error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>/regenerate-code', methods=['POST'])
def regenerate_course_code(course_id):
    """Regenerate course code."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Generate new 6-digit code
        import secrets
        new_code = f"{secrets.randbelow(900000) + 100000}"  # Random 6-digit number
        
        # Update course
        courses = getattr(app_state, 'courses', [])
        for course in courses:
            if course['id'] == course_id:
                course['code'] = new_code
                course['updated_at'] = datetime.now().isoformat()
                return jsonify({'success': True, 'code': new_code})
        
        return jsonify({'error': 'Course not found'}), 404
    except Exception as e:
        logger.error(f"Regenerate code error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>/archive', methods=['POST'])
def archive_course(course_id):
    """Archive/unarchive a course."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json() or {}
        archived = data.get('archived', True)
        
        courses = getattr(app_state, 'courses', [])
        for course in courses:
            if course['id'] == course_id:
                course['status'] = 'archived' if archived else 'active'
                course['updated_at'] = datetime.now().isoformat()
                return jsonify({'success': True, 'status': course['status']})
        
        return jsonify({'error': 'Course not found'}), 404
    except Exception as e:
        logger.error(f"Archive course error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>/materials', methods=['GET'])
def get_course_materials(course_id):
    """Get materials for a course."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get materials for this course
        materials = []
        if hasattr(app_state, 'course_materials'):
            materials = app_state.course_materials.get(course_id, [])
        
        return jsonify({'materials': materials})
    except Exception as e:
        logger.error(f"Get materials error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/courses/<course_id>/students', methods=['GET'])
def get_course_students(course_id):
    """Get enrolled students for a course."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Return mock student data - in production, query enrollment table
        students = []
        if hasattr(app_state, 'course_students'):
            students = app_state.course_students.get(course_id, [])
        
        return jsonify({'students': students})
    except Exception as e:
        logger.error(f"Get students error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ANALYTICS ENDPOINTS - Live from Supabase
# ============================================================================

@app.route('/api/analytics/<course_id>', methods=['GET'])
def get_course_analytics(course_id):
    """Get live analytics for a course from Supabase."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Fetch analytics from Supabase via Node.js API
        try:
            import requests
            
            # Get summary stats
            summary_response = requests.get(f"{NODE_API_URL}/api/analytics/summary/{course_id}", timeout=5)
            summary = summary_response.json() if summary_response.ok else {}
            
            # Get confusing topics
            topics_response = requests.get(f"{NODE_API_URL}/api/analytics/confusing-topics/{course_id}", timeout=5)
            confusing_topics = topics_response.json() if topics_response.ok else []
            
            # Get at-risk students
            atrisk_response = requests.get(f"{NODE_API_URL}/api/analytics/at-risk/{course_id}", timeout=5)
            at_risk_students = atrisk_response.json() if atrisk_response.ok else []
            
        except Exception as api_error:
            logger.warning(f"Supabase API unavailable, using fallback: {api_error}")
            summary = {
                'total_queries': 0,
                'active_students': 0,
                'avg_confidence': 0,
                'engagement_trend': []
            }
            confusing_topics = []
            at_risk_students = []
        
        # Get number of docs uploaded
        try:
            materials_response = requests.get(f"{NODE_API_URL}/api/materials/{course_id}", timeout=5)
            materials = materials_response.json() if materials_response.ok else []
            docs_uploaded = len(materials)
        except:
            docs_uploaded = 0
        
        analytics = {
            'total_queries': summary.get('total_queries', 0),
            'active_students': summary.get('active_students', 0),
            'avg_confidence': summary.get('avg_confidence', 0),
            'docs_uploaded': docs_uploaded,
            'confusing_topics': confusing_topics,
            'at_risk_students': at_risk_students,
            'engagement_trend': summary.get('engagement_trend', [])
        }
        
        return jsonify(analytics)
    except Exception as e:
        logger.error(f"Get analytics error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/<course_id>/queries', methods=['GET'])
def get_course_queries(course_id):
    """Get recent queries for a course from Supabase."""
    try:
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Fetch queries from Supabase
        try:
            import requests
            response = requests.get(f"{NODE_API_URL}/api/queries/{course_id}", timeout=5)
            queries = response.json() if response.ok else []
            
            # Convert to format expected by frontend
            formatted_queries = []
            for q in queries:
                formatted_queries.append({
                    'topic': q.get('topics', ['General'])[0] if q.get('topics') else 'General',
                    'time': q.get('created_at', '')[:16].replace('T', ' '),
                    'student': f"STU_{q.get('student_id', '')[:4].upper()}" if q.get('student_id') else 'STU_XXXX',
                    'text': q.get('question', ''),
                    'response': q.get('answer', ''),
                    'sources': ', '.join(q.get('sources_used', [])),
                    'failed': not q.get('answer') or q.get('confidence_score', 0) < 0.3
                })
            
            return jsonify({'queries': formatted_queries})
        except Exception as api_error:
            logger.warning(f"Failed to fetch queries: {api_error}")
            return jsonify({'queries': []})
    except Exception as e:
        logger.error(f"Get queries error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STUDENT API COMPATIBILITY (for studentHome.js)
# ============================================================================

@app.route('/users/<user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Get user by ID (for student home page)."""
    try:
        # Check authentication
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # If requesting different user, only teachers can see other users
        if str(user.id) != str(user_id) and user.role != 'teacher':
            return jsonify({'error': 'Forbidden'}), 403
        
        return jsonify({
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'first_name': user.full_name.split()[0] if user.full_name else 'Student',
            'role': user.role
        })
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/studentcourses/<user_id>', methods=['GET'])
def get_student_courses(user_id):
    """Get courses for a student."""
    try:
        # Check authentication
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get student's enrolled courses
        courses = []
        if hasattr(app_state, 'enrollments'):
            course_ids = app_state.enrollments.get(str(user_id), [])
            for cid in course_ids:
                course = next((c for c in getattr(app_state, 'courses', []) if c['id'] == cid), None)
                if course:
                    courses.append(course)
        
        return jsonify(courses)
    except Exception as e:
        logger.error(f"Get student courses error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/addCourse/<user_id>/<course_id>', methods=['POST'])
def add_course_enrollment(user_id, course_id):
    """Add course enrollment for a student by course code."""
    try:
        # Check authentication
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Teachers can enroll students; students enroll themselves
        # Use logged-in user's ID
        actual_user_id = user.user_id
        actual_user_role = user.role
        
        # Verify course exists (by ID or by code)
        course = None
        course_code = str(course_id)
        
        # Try as course ID first
        all_courses = getattr(app_state, 'courses', [])
        course = next((c for c in all_courses if c['id'] == course_id), None)
        
        # If not found, try as numeric code
        if not course:
            course = next((c for c in all_courses if str(c.get('code', '')) == course_code), None)
        
        if not course:
            return jsonify({'error': 'Course not found. Check the code and try again.'}), 404
        
        real_course_id = course['id']
        
        # Add enrollment
        if not hasattr(app_state, 'enrollments'):
            app_state.enrollments = {}
        
        enrollments = app_state.enrollments
        user_key = str(actual_user_id)
        
        if user_key not in enrollments:
            enrollments[user_key] = []
        
        if real_course_id not in enrollments[user_key]:
            enrollments[user_key].append(real_course_id)
            course['students_count'] = course.get('students_count', 0) + 1
            logger.info(f"Student {user.email} enrolled in {course['name']}")
        
        return jsonify({'success': True, 'course': course})
    except Exception as e:
        logger.error(f"Add course error: {e}")
        return jsonify({'error': str(e)}), 500


# Also need to add course enrollment for Node.js-style code lookup
@app.route('/course/code/<course_code>', methods=['GET'])
def get_course_by_code(course_code):
    """Get course by course code."""
    try:
        course_code = course_code.upper()
        
        # Fetch from Supabase via Express API
        try:
            response = requests.get(f"{NODE_API_URL}/course/code/{course_code}", timeout=10)
            if response.status_code == 200:
                course = response.json()
                return jsonify({
                    'id': course.get('id'),
                    'course_id': course.get('id'),
                    'name': course.get('name'),
                    'code': course.get('code')
                })
            else:
                return jsonify({'error': 'Course not found'}), 404
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'error': 'Database connection error'}), 500
            
    except Exception as e:
        logger.error(f"Get course by code error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/course', methods=['GET'])
def get_all_courses():
    """Get all courses."""
    try:
        # Fetch from Supabase via Express API
        try:
            response = requests.get(f"{NODE_API_URL}/course", timeout=10)
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                return jsonify([])
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify([])
    except Exception as e:
        logger.error(f"Get courses error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/course/<course_id>', methods=['GET'])
def get_course_by_id(course_id):
    """Get course by ID."""
    try:
        # Fetch from Supabase via Express API
        try:
            response = requests.get(f"{NODE_API_URL}/course/{course_id}", timeout=10)
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                return jsonify({'error': 'Course not found'}), 404
        except requests.RequestException as e:
            logger.error(f"Error calling Express API: {e}")
            return jsonify({'error': 'Database connection error'}), 500
    except Exception as e:
        logger.error(f"Get course error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    """Render the login page."""
    return redirect('/login')


@app.route('/login')
def login_page():
    """Render the login page."""
    return render_template('login.html')


@app.route('/student/home')
def student_home():
    """Student dashboard/home page."""
    return render_template('studentHome.html')


@app.route('/instructor/dashboard')
def instructor_dashboard():
    """Instructor dashboard page."""
    try:
        template_path = os.path.join(BASE_DIR, '..', 'frontend', 'instructor', 'templates', 'instructor', 'dashboard.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace static path for instructor CSS
        content = content.replace('{{ url_for(\'static\', filename=\'css/instructor.css\') }}', '/static/instructor/css/instructor.css')
        
        # Simple template rendering with user info placeholder
        return content.replace('{{user_name}}', 'Instructor').replace('{{course_count}}', '0')
    except Exception as e:
        logger.error(f"Instructor dashboard error: {e}")
        abort(500)


@app.route('/instructor/course/<course_id>')
def instructor_course(course_id):
    """Instructor course view."""
    try:
        template_path = os.path.join(BASE_DIR, '..', 'frontend', 'instructor', 'templates', 'instructor', 'course.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix static path for instructor CSS
        content = content.replace('{{ url_for(\'static\', filename=\'css/instructor.css\') }}', '/static/instructor/css/instructor.css')
        
        return content.replace('{{course_id}}', course_id)
    except Exception as e:
        logger.error(f"Instructor course error: {e}")
        abort(500)


@app.route('/instructor/analytics/<course_id>')
def instructor_analytics(course_id):
    """Instructor analytics view."""
    try:
        template_path = os.path.join(BASE_DIR, '..', 'frontend', 'instructor', 'templates', 'instructor', 'analytics.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix static path for instructor CSS
        content = content.replace('{{ url_for(\'static\', filename=\'css/instructor.css\') }}', '/static/instructor/css/instructor.css')
        
        return content.replace('{{course_id}}', course_id)
    except Exception as e:
        logger.error(f"Instructor analytics error: {e}")
        abort(500)

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    # Check which embedding provider is configured
    embedding_provider = os.environ.get('EMBEDDING_PROVIDER', '').lower()
    is_gemini = embedding_provider == 'gemini' and os.environ.get('GOOGLE_API_KEY')
    
    # Determine actual provider based on what was initialized
    actual_provider = 'sentence-transformers'  # Default
    if hasattr(app_state, 'actual_embedding_provider'):
        actual_provider = app_state.actual_embedding_provider
    
    return jsonify({
        'status': 'ok',
        'rag_initialized': app_state.is_initialized,
        'files_uploaded': len(app_state.uploaded_files),
        'embedding_provider': actual_provider,
        'embedding_dimension': app_state.embedding_manager.get_embedding_dimension() if app_state.embedding_manager else 'N/A',
        'gemini_requested': is_gemini,
        'gemini_compatible': False,  # Python 3.14 not compatible
        'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
        'langchain': LANGCHAIN_AVAILABLE,
        'whisper': WHISPER_AVAILABLE,
        'multimodal_pdf': MULTIMODAL_AVAILABLE,
        'relevance_scorer': RELEVANCE_SCORER_AVAILABLE and app_state.relevance_scorer is not None,
        'multimodal_features': {
            'image_analysis': True,
            'table_analysis': True,
            'audio_diarization': True,
            'relevance_scoring': RELEVANCE_SCORER_AVAILABLE and app_state.relevance_scorer is not None,
            'multimodal_api_endpoints': True
        }
    })

@app.route('/api/initialize', methods=['POST'])
def initialize():
    """Initialize the RAG application."""
    try:
        if not app_state.is_initialized:
            app_state.initialize()
        
        # Check which embedding provider is being used
        embedding_provider = os.environ.get('EMBEDDING_PROVIDER', '').lower()
        is_gemini = embedding_provider == 'gemini' and os.environ.get('GOOGLE_API_KEY')
        
        return jsonify({
            'success': True,
            'message': 'RAG application initialized',
            'embedding_provider': 'gemini' if is_gemini else 'sentence-transformers',
            'embedding_dimension': app_state.embedding_manager.get_embedding_dimension() if app_state.embedding_manager else 'N/A',
            'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
            'langchain': LANGCHAIN_AVAILABLE,
            'whisper': WHISPER_AVAILABLE,
            'multimodal': MULTIMODAL_AVAILABLE,
            'relevance_scorer': RELEVANCE_SCORER_AVAILABLE and app_state.relevance_scorer is not None,
            'multimodal_features': {
                'image_analysis': True,
                'table_analysis': True,
                'audio_diarization': True,
                'relevance_scoring': RELEVANCE_SCORER_AVAILABLE and app_state.relevance_scorer is not None,
                'multimodal_api_endpoints': True
            }
        })
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload (documents and images)."""
    try:
        logger.info("=== UPLOAD REQUEST STARTED ===")
        
        # Initialize if needed
        if not app_state.is_initialized:
            logger.info("Initializing app state...")
            app_state.initialize()
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Check if it's an image file - if so, process as image
        if allowed_image(file.filename):
            # Process as image - delegate to image upload logic
            return process_image_upload(file)
        
        # Otherwise, process as document
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'
            }), 400
        
        # Save the file
        file_id = generate_file_id()
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        logger.info(f"File saved: {file_path}")
        
        # Process the file
        logger.info(f"Processing file: {file_path}")
        result = process_uploaded_file(file_path, file_id)
        
        logger.info(f"Processing result: {result}")
        
        if not result['success']:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def process_image_upload(file) -> Any:
    """Process an image file upload (used by both endpoints)."""
    try:
        # Validate image
        validation = validate_image_file(file)
        if not validation['valid']:
            return jsonify({'success': False, 'error': validation['error']}), 400
        
        # Save the file
        file_id = generate_file_id()
        filename = secure_filename(file.filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        logger.info(f"Image saved: {file_path}")
        
        # Process the image
        result = process_image_file(file_path, file_id)
        
        # Store file info in app_state regardless of processing success
        # so the user can see the image in the UI even if analysis failed
        if not hasattr(app_state, 'uploaded_images'):
            app_state.uploaded_images = {}
        
        app_state.uploaded_images[file_id] = {
            'file_path': file_path,
            'file_name': filename,
            'upload_time': datetime.now().isoformat(),
            'description': result.get('description'),
            'has_error': not result['success'],
            'error_message': result.get('error')
        }
        
        # Return success even if analysis had issues, but include error info
        # The file is kept and shown in UI
        status_code = 200 if result['success'] else 200  # Always 200 to keep file
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    """Handle image file upload for vision model processing."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        validation = validate_image_file(file)
        if not validation['valid']:
            return jsonify({'success': False, 'error': validation['error']}), 400
        
        file_id = generate_file_id()
        filename = secure_filename(file.filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        logger.info(f"Image saved: {file_path}")
        
        result = process_image_file(file_path, file_id)
        
        # Store file info in app_state regardless of processing success
        if not hasattr(app_state, 'uploaded_images'):
            app_state.uploaded_images = {}
        
        app_state.uploaded_images[file_id] = {
            'file_path': file_path,
            'file_name': filename,
            'upload_time': datetime.now().isoformat(),
            'description': result.get('description'),
            'has_error': not result['success'],
            'error_message': result.get('error')
        }
        
        # Return 200 even if analysis failed, so file is kept
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images', methods=['GET'])
def list_images():
    """List all uploaded images."""
    try:
        images = []
        if hasattr(app_state, 'uploaded_images'):
            for image_id, info in app_state.uploaded_images.items():
                images.append({
                    'file_id': image_id,
                    'file_name': info['file_name'],
                    'upload_time': info['upload_time'],
                    'description': info.get('description', '')[:100] + '...' if info.get('description') else None
                })
        return jsonify({'success': True, 'images': images})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/images/<file_id>', methods=['DELETE'])
def delete_image(file_id):
    """Delete an uploaded image."""
    try:
        if not hasattr(app_state, 'uploaded_images') or file_id not in app_state.uploaded_images:
            return jsonify({'success': False, 'error': 'Image not found'}), 404
        
        info = app_state.uploaded_images[file_id]
        if os.path.exists(info['file_path']):
            os.remove(info['file_path'])
        
        del app_state.uploaded_images[file_id]
        
        return jsonify({'success': True, 'message': 'Image deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def query():
    """Handle query request with course scoping and Supabase tracking."""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'error': 'No question provided'
            }), 400
        
        question = data['question'].strip()
        course_id = data.get('course_id')  # Optional course_id for scoping
        
        if not question:
            return jsonify({
                'success': False,
                'error': 'Empty question'
            }), 400
        
        # Get session for user info
        token = request.cookies.get('session_token')
        user = None
        if token:
            user = auth_session.get_session(token)
        
        # Check for uploaded images first
        has_images = hasattr(app_state, 'uploaded_images') and app_state.uploaded_images
        has_documents = app_state.uploaded_files
        
        # If neither documents nor images, return error
        if not has_documents and not has_images:
            return jsonify({
                'success': False,
                'error': 'No documents or images uploaded for this course. Please upload files first.'
            }), 400
        
        # If we have images but no documents, answer based on image descriptions
        if has_images and not has_documents:
            # Answer based on uploaded images, but only those that were successfully analyzed
            image_results = []
            failed_images = []
            
            for image_id, info in app_state.uploaded_images.items():
                description = info.get('description', 'No description available')
                # Skip images that failed analysis (indicated by has_error flag or error in description)
                if info.get('has_error', False) or (description and ('failed' in description.lower() or 'error' in description.lower())):
                    failed_images.append(info['file_name'])
                    continue
                image_results.append({
                    'file_name': info['file_name'],
                    'description': description
                })
            
            if not image_results:
                return jsonify({
                    'success': False,
                    'error': 'No images were successfully analyzed. Please try uploading images again or use a different image.',
                    'failed_images': failed_images
                }), 400
            
            # Generate answer from image descriptions
            answer_text = "I analyzed the following uploaded images:\n\n"
            for idx, img in enumerate(image_results, 1):
                answer_text += f"### Image {idx}: {img['file_name']}\n"
                answer_text += f"{img['description']}\n\n"
            
            # Add the user's question context
            answer_text += f"---\n\n**Your question:** {question}\n\n"
            
            if failed_images:
                answer_text += f"\nNote: {len(failed_images)} image(s) could not be analyzed: {', '.join(failed_images)}\n"
            
            return jsonify({
                'success': True,
                'answer': answer_text,
                'citations': [],
                'source_type': 'images'
            })
        
        # Course-scoped document-based RAG
        max_results = data.get('max_results', 5)
        result = retrieve_and_answer(question, max_results=max_results, course_id=course_id)
        
        # If we also have images, include them in the response
        if has_images:
            result['has_images'] = True
            result['image_count'] = len(app_state.uploaded_images)
        
        # Track query to Supabase (async, don't wait)
        if user and course_id:
            try:
                import threading
                def track_query():
                    try:
                        # Import requests if not already imported
                        import requests
                        requests.post(
                            f"{NODE_API_URL}/api/queries",
                            json={
                                'course_id': course_id,
                                'student_id': str(user.id),
                                'question': question,
                                'answer': result.get('answer', ''),
                                'sources_used': [c.get('source_file', '') for c in result.get('citations', [])],
                                'confidence_score': result.get('confidence', 0)
                            },
                            timeout=5
                        )
                    except Exception as e:
                        logger.warning(f"Failed to track query: {e}")
                
                # Run in background thread
                threading.Thread(target=track_query, daemon=True).start()
            except Exception as e:
                logger.warning(f"Query tracking setup failed: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """List all uploaded files."""
    try:
        files = []
        for file_id, info in app_state.uploaded_files.items():
            files.append({
                'file_id': file_id,
                'file_name': info['filename'],  # Standardized: use 'file_name' for consistency
                'file_type': info['file_type'].replace('.', ''),  # e.g., 'pdf' not '.pdf'
                'chunks': info.get('chunks', 0),
                'upload_time': info['upload_time']
            })
        
        return jsonify({
            'success': True,
            'files': files,
            'total_files': len(files)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/clear', methods=['POST'])
def clear_all():
    """Clear all uploaded files."""
    try:
        app_state.uploaded_files.clear()
        
        # Reinitialize vector store
        if app_state.is_initialized:
            app_state.vector_store = SimpleVectorStore(
                dimension=app_state.embedding_manager.get_embedding_dimension()
            )
        
        return jsonify({
            'success': True,
            'message': 'All documents cleared'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# MULTIMODAL CONTENT API ENDPOINTS
# ============================================================================

@app.route('/api/multimodal/content/<file_id>', methods=['GET'])
def get_multimodal_content(file_id):
    """
    Get all multimodal content (images, tables, audio) for a specific file.
    
    Returns structured multimodal content with analysis metadata.
    """
    try:
        if not app_state.is_initialized:
            return jsonify({'success': False, 'error': 'Application not initialized'}), 400
        
        # Check if file exists
        if file_id not in app_state.uploaded_files:
            return jsonify({'success': False, 'error': f'File {file_id} not found'}), 404
        
        file_info = app_state.uploaded_files[file_id]
        
        # Search vector store for chunks belonging to this file
        all_chunks = app_state.vector_store.documents
        file_chunks = []
        
        for doc in all_chunks:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            if metadata.get('document_id') == file_id or metadata.get('filename') == file_info.get('filename'):
                file_chunks.append(doc)
        
        # Organize by content type
        images = []
        tables = []
        audio_segments = []
        text_chunks = []
        
        for chunk in file_chunks:
            metadata = chunk.metadata if hasattr(chunk, 'metadata') else {}
            content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
            element_type = metadata.get('element_type', metadata.get('chunk_type', 'text'))
            
            if element_type == 'image':
                images.append({
                    'index': len(images),
                    'content': content,
                    'description': metadata.get('description', metadata.get('image_caption', '')),
                    'keywords': metadata.get('keywords', []),
                    'chart_type': metadata.get('chart_type', 'unknown'),
                    'chart_title': metadata.get('chart_title', ''),
                    'subject_area': metadata.get('subject_area', 'unknown'),
                    'confidence_scores': metadata.get('confidence_scores', {}),
                    'page_number': metadata.get('page_number', 1)
                })
            elif element_type == 'table':
                tables.append({
                    'index': len(tables),
                    'content': content,
                    'markdown_table': content,
                    'analysis': metadata.get('analysis', ''),
                    'rows': metadata.get('rows', 0),
                    'columns': metadata.get('columns', 0),
                    'table_structure': metadata.get('table_structure', {}),
                    'column_details': metadata.get('column_details', []),
                    'patterns_insights': metadata.get('patterns_insights', []),
                    'data_quality': metadata.get('data_quality', {}),
                    'page_number': metadata.get('page_number', 1)
                })
            elif element_type == 'audio':
                audio_segments.append({
                    'index': len(audio_segments),
                    'content': content,
                    'timestamp': metadata.get('timestamp_str', ''),
                    'timestamp_seconds': metadata.get('timestamp', 0),
                    'speaker': metadata.get('speaker', 'Unknown'),
                    'tone': metadata.get('tone', 'neutral'),
                    'confidence': metadata.get('confidence', 0.8),
                    'is_speaker_change': metadata.get('is_speaker_change', False)
                })
            else:
                text_chunks.append({
                    'index': len(text_chunks),
                    'content': content[:500],
                    'page_number': metadata.get('page_number', 1)
                })
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': file_info.get('filename', 'Unknown'),
            'file_type': file_info.get('file_type', 'unknown'),
            'multimodal_content': {
                'images': images,
                'tables': tables,
                'audio_segments': audio_segments,
                'text_chunks': text_chunks
            },
            'counts': {
                'images': len(images),
                'tables': len(tables),
                'audio_segments': len(audio_segments),
                'text_chunks': len(text_chunks)
            }
        })
        
    except Exception as e:
        logger.error(f"Multimodal content error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/multimodal/search', methods=['GET'])
def search_multimodal():
    """
    Search specifically for multimodal content (images, tables, audio).
    
    Query parameters:
    - q: Search query (required)
    - type: Content type filter (image, table, audio, or all)
    - limit: Maximum results to return (default: 10)
    """
    try:
        if not app_state.is_initialized:
            return jsonify({'success': False, 'error': 'Application not initialized'}), 400
        
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'success': False, 'error': 'Search query (q) is required'}), 400
        
        content_type = request.args.get('type', 'all').lower()
        limit = int(request.args.get('limit', 10))
        
        # Embed query
        query_embedding = app_state.embedding_manager.embed_query(query)
        
        # Search vector store
        search_results = app_state.vector_store.similarity_search(
            query_embedding=query_embedding,
            k=limit * 2  # Get more for filtering
        )
        
        # Filter by content type if specified
        filtered_results = []
        for doc in search_results:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            element_type = metadata.get('element_type', metadata.get('chunk_type', 'text'))
            
            if content_type == 'all' or element_type == content_type:
                content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                result = {
                    'content': content[:300],
                    'element_type': element_type,
                    'similarity_score': metadata.get('similarity_score', 0),
                    'source_file': metadata.get('filename', 'Unknown'),
                    'page_number': metadata.get('page_number', 'N/A')
                }
                
                # Add type-specific metadata
                if element_type == 'image':
                    result['description'] = metadata.get('description', '')
                    result['chart_type'] = metadata.get('chart_type', 'unknown')
                elif element_type == 'table':
                    result['analysis'] = metadata.get('analysis', '')
                    result['rows'] = metadata.get('rows', 0)
                    result['columns'] = metadata.get('columns', 0)
                elif element_type == 'audio':
                    result['speaker'] = metadata.get('speaker', 'Unknown')
                    result['timestamp'] = metadata.get('timestamp_str', '')
                    result['tone'] = metadata.get('tone', 'neutral')
                
                filtered_results.append(result)
        
        # Apply relevance scoring if available
        if app_state.relevance_scorer and filtered_results:
            try:
                reranked = app_state.relevance_scorer.rerank_results(query, search_results, top_k=limit)
                # Update scores in filtered results
                score_map = {}
                for chunk, score, breakdown in reranked:
                    content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
                    score_map[content[:300]] = {'relevance_score': score, 'breakdown': breakdown}
                
                for r in filtered_results:
                    if r['content'] in score_map:
                        r['relevance_score'] = score_map[r['content']]['relevance_score']
                        r['relevance_breakdown'] = score_map[r['content']]['breakdown']
            except Exception as e:
                logger.warning(f"Relevance scoring failed: {e}")
        
        return jsonify({
            'success': True,
            'query': query,
            'content_type_filter': content_type,
            'results': filtered_results[:limit],
            'total_found': len(filtered_results)
        })
        
    except Exception as e:
        logger.error(f"Multimodal search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/multimodal/image/<file_id>/<int:index>', methods=['GET'])
def get_image_content(file_id, index):
    """Serve image data with metadata for a specific file and image index."""
    try:
        if not app_state.is_initialized:
            return jsonify({'success': False, 'error': 'Application not initialized'}), 400
        
        if file_id not in app_state.uploaded_files:
            return jsonify({'success': False, 'error': f'File {file_id} not found'}), 404
        
        # Find the image chunk
        all_docs = app_state.vector_store.documents
        image_chunks = [
            doc for doc in all_docs 
            if hasattr(doc, 'metadata') and 
               doc.metadata.get('document_id') == file_id and
               doc.metadata.get('element_type', doc.metadata.get('chunk_type')) == 'image'
        ]
        
        if index >= len(image_chunks):
            return jsonify({'success': False, 'error': f'Image index {index} out of range (found {len(image_chunks)} images)'}), 404
        
        chunk = image_chunks[index]
        metadata = chunk.metadata
        
        response_data = {
            'success': True,
            'file_id': file_id,
            'image_index': index,
            'content': chunk.page_content if hasattr(chunk, 'page_content') else str(chunk),
            'metadata': {
                'description': metadata.get('description', ''),
                'keywords': metadata.get('keywords', []),
                'chart_type': metadata.get('chart_type', 'unknown'),
                'chart_title': metadata.get('chart_title', ''),
                'chart_caption': metadata.get('chart_caption', ''),
                'data_points': metadata.get('data_points', []),
                'trends': metadata.get('trends', []),
                'text_blocks': metadata.get('text_blocks', []),
                'axes_info': metadata.get('axes_info', {}),
                'legends_info': metadata.get('legends_info', []),
                'subject_area': metadata.get('subject_area', 'unknown'),
                'document_type': metadata.get('document_type', 'unknown'),
                'objects_detected': metadata.get('objects_detected', []),
                'confidence_scores': metadata.get('confidence_scores', {}),
                'page_number': metadata.get('page_number', 1)
            }
        }
        
        # Include image data if available (base64)
        if metadata.get('has_image_data'):
            response_data['image_data_available'] = True
            response_data['image_url'] = f"/api/multimodal/image/{file_id}/{index}/data"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Image content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/multimodal/table/<file_id>/<int:index>', methods=['GET'])
def get_table_content(file_id, index):
    """Serve table data in multiple formats for a specific file and table index."""
    try:
        if not app_state.is_initialized:
            return jsonify({'success': False, 'error': 'Application not initialized'}), 400
        
        if file_id not in app_state.uploaded_files:
            return jsonify({'success': False, 'error': f'File {file_id} not found'}), 404
        
        # Find table chunks
        all_docs = app_state.vector_store.documents
        table_chunks = [
            doc for doc in all_docs 
            if hasattr(doc, 'metadata') and 
               doc.metadata.get('document_id') == file_id and
               doc.metadata.get('element_type', doc.metadata.get('chunk_type')) == 'table'
        ]
        
        if index >= len(table_chunks):
            return jsonify({'success': False, 'error': f'Table index {index} out of range (found {len(table_chunks)} tables)'}), 404
        
        chunk = table_chunks[index]
        metadata = chunk.metadata
        content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
        
        return jsonify({
            'success': True,
            'file_id': file_id,
            'table_index': index,
            'markdown_table': content,
            'analysis': metadata.get('analysis', ''),
            'metadata': {
                'rows': metadata.get('rows', 0),
                'columns': metadata.get('columns', 0),
                'table_structure': metadata.get('table_structure', {}),
                'column_details': metadata.get('column_details', []),
                'relationships': metadata.get('relationships', []),
                'patterns_insights': metadata.get('patterns_insights', []),
                'data_quality': metadata.get('data_quality', {}),
                'suggested_visualizations': metadata.get('suggested_visualizations', []),
                'potential_use_cases': metadata.get('potential_use_cases', []),
                'confidence_scores': metadata.get('confidence_scores', {}),
                'has_numeric_data': metadata.get('has_numeric_data', False),
                'has_date_data': metadata.get('has_date_data', False),
                'key_columns': metadata.get('key_columns', []),
                'page_number': metadata.get('page_number', 1)
            }
        })
        
    except Exception as e:
        logger.error(f"Table content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/multimodal/audio/<file_id>/<int:segment_index>', methods=['GET'])
def get_audio_content(file_id, segment_index):
    """Serve audio segment data with timestamps and speaker info."""
    try:
        if not app_state.is_initialized:
            return jsonify({'success': False, 'error': 'Application not initialized'}), 400
        
        if file_id not in app_state.uploaded_files:
            return jsonify({'success': False, 'error': f'File {file_id} not found'}), 404
        
        # Find audio chunks
        all_docs = app_state.vector_store.documents
        audio_chunks = [
            doc for doc in all_docs 
            if hasattr(doc, 'metadata') and 
               doc.metadata.get('document_id') == file_id and
               doc.metadata.get('element_type', doc.metadata.get('chunk_type')) == 'audio'
        ]
        
        if segment_index >= len(audio_chunks):
            return jsonify({'success': False, 'error': f'Segment index {segment_index} out of range (found {len(audio_chunks)} segments)'}), 404
        
        chunk = audio_chunks[segment_index]
        metadata = chunk.metadata
        content = chunk.page_content if hasattr(chunk, 'page_content') else str(chunk)
        
        # Check if this is the full transcript chunk
        is_full_transcript = metadata.get('is_full_transcript', False)
        
        response = {
            'success': True,
            'file_id': file_id,
            'segment_index': segment_index,
            'is_full_transcript': is_full_transcript,
            'content': content,
            'metadata': {
                'timestamp': metadata.get('timestamp_str', ''),
                'timestamp_seconds': metadata.get('timestamp', 0),
                'speaker': metadata.get('speaker', 'Unknown'),
                'tone': metadata.get('tone', 'neutral'),
                'confidence': metadata.get('confidence', 0.8),
                'word_count': metadata.get('word_count', 0),
                'is_speaker_change': metadata.get('is_speaker_change', False)
            }
        }
        
        # Add full transcript metadata if available
        if is_full_transcript:
            response['metadata']['unique_speakers'] = metadata.get('unique_speakers', [])
            response['metadata']['diarization_success'] = metadata.get('diarization_success', False)
            response['metadata']['audio_quality'] = metadata.get('audio_quality', 'unknown')
            response['metadata']['background_noise'] = metadata.get('background_noise', 'none detected')
            response['metadata']['language_detected'] = metadata.get('language_detected', 'unknown')
            response['metadata']['estimated_speakers'] = metadata.get('estimated_speakers', 1)
            response['metadata']['speech_rate_wpm'] = metadata.get('speech_rate_wpm', 0.0)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Audio content error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# GOOGLE DRIVE INTEGRATION
# ============================================================================

import re

# ============================================
# GOOGLE OAUTH FUNCTIONS
# ============================================

def get_drive_config():
    """Get Google Drive OAuth configuration."""
    return {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        'redirect_uri': os.environ.get('GOOGLE_REDIRECT_URI', ''),
    }


def build_drive_auth_url(state_token: str) -> str:
    """Build Google OAuth consent URL."""
    config = get_drive_config()
    if not config['client_id']:
        return None
    
    params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'https://www.googleapis.com/auth/drive.readonly',
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state_token,
    }
    from urllib.parse import urlencode
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_drive_code(code: str) -> dict:
    """Exchange OAuth code for tokens."""
    import requests
    config = get_drive_config()
    
    if not config['client_id']:
        return {'error': 'Google OAuth not configured'}
    
    data = {
        'code': code,
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'redirect_uri': config['redirect_uri'],
        'grant_type': 'authorization_code',
    }
    
    try:
        response = requests.post('https://oauth2.googleapis.com/token', data=data, timeout=30)
        if response.ok:
            return response.json()
        return {'error': f'Token exchange failed: {response.status_code}'}
    except Exception as e:
        return {'error': str(e)}


@app.route('/drive/auth')
def drive_auth_start():
    """Start OAuth flow."""
    try:
        course_id = request.args.get('course_id')
        if not course_id:
            return jsonify({'error': 'course_id required'}), 400
        
        import secrets
        state = secrets.token_urlsafe(32)
        session['drive_oauth_state'] = state
        session['drive_oauth_course'] = course_id
        
        auth_url = build_drive_auth_url(state)
        if not auth_url:
            return jsonify({'error': 'Google OAuth not configured'}), 500
        
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Auth start error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drive/callback')
def drive_auth_callback():
    """Handle OAuth callback."""
    try:
        error = request.args.get('error')
        if error:
            return jsonify({'error': error}), 400
        
        code = request.args.get('code')
        state = request.args.get('state')
        
        expected_state = session.get('drive_oauth_state')
        if state != expected_state:
            return jsonify({'error': 'Invalid state'}), 400
        
        course_id = session.pop('drive_oauth_course', None)
        
        tokens = exchange_drive_code(code)
        if 'error' in tokens:
            return jsonify({'error': tokens['error']}), 500
        
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        
        if not access_token:
            return jsonify({'error': 'No access token'}), 500
        
        # Store tokens in session
        session['drive_access_token'] = access_token
        session['drive_refresh_token'] = refresh_token
        
        logger.info(f"Drive connected for course: {course_id}")
        
        return redirect(f'/instructor/course/{course_id}')
    except Exception as e:
        logger.error(f"Auth callback error: {e}")
        return jsonify({'error': str(e)}), 500


def extract_drive_folder_id(url: str) -> str:
    """Extract folder ID from Google Drive URL."""
    patterns = [
        r'drive\.google\.com/folderview\?id=([^&]+)',
        r'drive\.google\.com/[a-z/]+/folders/([^&]+)',
        r'docs\.google\.com/[^/]+/folders/([^&]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Try generic base64-like ID
    match = re.search(r'([a-zA-Z0-9_-]{20,})', url)
    if match:
        return match.group(1)
    
    return None


@app.route('/drive/connect', methods=['POST'])
def connect_drive():
    """Connect Google Drive with a folder URL."""
    try:
        data = request.get_json()
        folder_url = data.get('folder_url', '')
        course_id = data.get('course_id')
        
        if not folder_url or not course_id:
            return jsonify({'error': 'folder_url and course_id required'}), 400
        
        folder_id = extract_drive_folder_id(folder_url)
        if not folder_id:
            return jsonify({'error': 'Invalid Google Drive URL'}), 400
        
        # Store in Supabase
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user = auth_session.get_session(token)
        if not user or user.role != 'teacher':
            return jsonify({'error': 'Teacher access required'}), 403
        
        try:
            import requests
            response = requests.post(
                f"{NODE_API_URL}/api/drive/connect",
                json={
                    'course_id': course_id,
                    'teacher_id': str(user.id),
                    'folder_url': folder_url,
                    'refresh_token': folder_id
                },
                timeout=5
            )
            
            if response.ok:
                logger.info(f"Drive connected: course={course_id}, folder={folder_id}")
                return jsonify({'success': True, 'folder_id': folder_id})
            else:
                return jsonify({'error': 'Failed to save Drive connection'}), 500
                
        except Exception as api_error:
            logger.warning(f"Supabase API unavailable: {api_error}")
            # Still return success - we'll use in-memory as fallback
            return jsonify({'success': True, 'folder_id': folder_id, 'mode': 'memory'})
            
    except Exception as e:
        logger.error(f"Drive connect error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drive/files/<course_id>', methods=['GET'])
def list_drive_files(course_id):
    """List files in connected Google Drive folder."""
    try:
        import requests
        response = requests.get(f"{NODE_API_URL}/api/drive/{course_id}", timeout=5)
        
        if not response.ok or not response.json():
            return jsonify({'error': 'Drive not connected', 'files': []}), 400
        
        drive_info = response.json()
        folder_url = drive_info.get('folder_url', '')
        folder_id = extract_drive_folder_id(folder_url)
        
        if not folder_id:
            return jsonify({'files': [], 'note': 'No folder linked'}), 200
        
        return jsonify({
            'files': [],
            'note': 'OAuth integration required for file listing',
            'folder_id': folder_id,
            'folder_url': folder_url
        }), 200
        
    except Exception as e:
        logger.error(f"Drive files error: {e}")
        return jsonify({'error': str(e), 'files': []}), 500


@app.route('/drive/sync', methods=['POST'])
def sync_drive_files():
    """Sync selected files from Google Drive."""
    try:
        data = request.get_json()
        file_urls = data.get('file_urls', [])
        course_id = data.get('course_id')
        
        if not file_urls or not course_id:
            return jsonify({'error': 'file_urls and course_id required'}), 400
        
        results = []
        
        # For each URL, we would download and vectorize
        # Full implementation requires OAuth credentials
        for url in file_urls:
            results.append({
                'url': url,
                'status': 'pending',
                'note': 'OAuth download pending'
            })
        
        return jsonify({'results': results}), 200
        
    except Exception as e:
        logger.error(f"Drive sync error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drive/embed', methods=['POST'])
def embed_drive_file():
    """Download file from Google Drive and vectorize it."""
    try:
        data = request.get_json()
        file_id = data.get('file_id')
        file_name = data.get('file_name', 'document')
        mime_type = data.get('mime_type', 'application/pdf')
        course_id = data.get('course_id')
        
        if not file_id or not course_id:
            return jsonify({'error': 'file_id and course_id required'}), 400
        
        # Get access token from session
        access_token = session.get('drive_access_token')
        
        if not access_token:
            return jsonify({'error': 'Google Drive not connected. Please link your Drive first.'}), 401
        
        logger.info(f"Downloading Drive file: {file_id}")
        
        # Download the file
        try:
            import requests
            from io import BytesIO
            
            # Export Google Docs to standard format
            export_mimes = {
                'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.spreadsheet': 'text/csv',
            }
            export_mime = export_mimes.get(mime_type)
            
            if export_mime:
                # Export Google Doc
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}/export'
                params = {'mimeType': export_mime}
            else:
                # Direct download
                url = f'https://www.googleapis.com/drive/v3/files/{file_id}'
                params = {'alt': 'media'}
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = requests.get(url, params=params, headers=headers, timeout=60)
            
            if not response.ok:
                return jsonify({'error': f'Download failed: {response.status_code}'}), 500
            
            content = response.content
            
            # Determine file extension
            ext = '.pdf'
            if mime_type == 'application/pdf':
                ext = '.pdf'
            elif 'document' in mime_type:
                ext = '.docx'
            elif 'spreadsheet' in mime_type:
                ext = '.csv'
            elif 'presentation' in mime_type:
                ext = '.pptx'
            else:
                ext = '.txt'
            
            # Save to temp file
            import tempfile
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, f"drive_{file_id}{ext}")
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"File saved to {file_path}")
            
        except Exception as download_error:
            logger.error(f"Download error: {download_error}")
            return jsonify({'error': f'Download failed: {str(download_error)}'}), 500
        
        # Now process and vectorize the file
        try:
            # Generate file ID
            file_id_new = generate_file_id()
            
            # Process the uploaded file
            result = process_uploaded_file(file_path, file_id_new)
            
            if result['success']:
                # Add course_id to metadata for scoping
                if hasattr(app_state, 'uploaded_files'):
                    if file_id_new in app_state.uploaded_files:
                        app_state.uploaded_files[file_id_new]['course_id'] = course_id
                        app_state.uploaded_files[file_id_new]['source'] = 'google_drive'
                
                # Record in Supabase
                try:
                    requests.post(
                        f"{NODE_API_URL}/api/materials",
                        json={
                            'course_id': course_id,
                            'source_type': 'google_drive',
                            'file_name': file_name,
                            'chunks_count': result.get('chunks', 0),
                            'file_id': file_id_new
                        },
                        timeout=5
                    )
                except:
                    pass
                
                return jsonify({
                    'success': True,
                    'file_id': file_id_new,
                    'filename': file_name,
                    'chunks': result.get('chunks', 0),
                    'message': f'Successfully embedded {file_name}'
                })
            else:
                return jsonify({'error': result.get('error', 'Processing failed')}), 500
                
        except Exception as vectorize_error:
            logger.error(f"Vectorize error: {vectorize_error}")
            return jsonify({'error': f'Vectorization failed: {str(vectorize_error)}'}), 500
        
    except Exception as e:
        logger.error(f"Embed error: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Initialize on startup (only once, not on reloader)
    if not app_state.is_initialized:
        app_state.initialize()
    
    # Run Flask (disable reloader to prevent double initialization issues)
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )
