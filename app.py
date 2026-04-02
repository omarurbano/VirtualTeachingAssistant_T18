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
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from NemotronNano import *

# Flask imports
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APPLICATION SETUP
# ============================================================================

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt', 'mp3', 'wav', 'ogg', 'm4a', 'flac'}
app.config['CHUNK_SIZE'] = 1000
app.config['CHUNK_OVERLAP'] = 200
app.config['MAX_CITATIONS'] = 10
app.config['SIMILARITY_THRESHOLD'] = 0.3

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ============================================================================
# DEPENDENCY CHECK
# ============================================================================

# Check and import dependencies
SENTENCE_TRANSFORMERS_AVAILABLE = False
LANGCHAIN_AVAILABLE = False
WHISPER_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("sentence-transformers available")
except ImportError:
    logger.warning("sentence-transformers not available")

try:
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain available")
except ImportError as e:
    logger.warning(f"LangChain not available: {e}")

try:
    import whisper
    WHISPER_AVAILABLE = True
    logger.info("Whisper available")
except ImportError:
    logger.warning("Whisper not available")

# ============================================================================
# SIMPLE DOCUMENT PROCESSING (STANDALONE)
# ============================================================================

class SimpleDocumentProcessor:
    """Standalone document processor when RAG modules are not available."""
    
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        
    def load_pdf(self, file_path: str) -> List[Any]:
        """Load PDF using PyPDFLoader."""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path)
            return loader.load()
        except Exception as e:
            logger.error(f"Error loading PDF: {e}")
            return []
    
    def load_docx(self, file_path: str) -> List[Any]:
        """Load Word document."""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            loader = Docx2txtLoader(file_path)
            return loader.load()
        except Exception as e:
            logger.error(f"Error loading DOCX: {e}")
            return []
    
    def load_text(self, file_path: str) -> List[Any]:
        """Load text file."""
        try:
            from langchain_community.document_loaders import TextLoader
            loader = TextLoader(file_path, encoding='utf-8')
            return loader.load()
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
        """Chunk documents into smaller pieces."""
        if not documents:
            return []
        return self.text_splitter.split_documents(documents)


class SimpleEmbeddingManager:
    """Standalone embedding manager."""
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.dimension = 384
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                self.dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"Loaded embedding model: {model_name}")
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
    """Simple answer generator."""
    
    def __init__(self, min_confidence=0.3):
        self.min_confidence = min_confidence
        
    def generate(self, query: str, retrieved_results: List[Dict], total_documents: int = 0):
        """Generate answer from retrieved results."""
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
        scores = [r.get('similarity_score', 0) for r in retrieved_results]
        best_score = max(scores) if scores else 0
        
        if best_score < self.min_confidence:
            return Result(
                answer_type='not_found',
                answer_text=f"I couldn't find relevant information. Best match similarity: {best_score:.2f}",
                reasoning="Content found but below confidence threshold.",
                confidence="none"
            )
        
        # Build answer from top results
        context_parts = []
        for r in retrieved_results[:3]:
            content = r.get('content', r.get('page_content', ''))[:200]
            context_parts.append(content)
        
        context = "\n\n".join(context_parts)
        
        answer = f"Based on the uploaded documents:\n\n{context}"
        
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
    """Process audio file using Whisper."""
    result = {
        'success': False,
        'text': '',
        'error': None
    }
    
    if not WHISPER_AVAILABLE:
        result['error'] = "Audio transcription not available. Install openai-whisper"
        return result
    
    try:
        logger.info(f"Transcribing audio: {file_path}")
        model = whisper.load_model("base")
        transcription = model.transcribe(file_path)
        result['success'] = True
        result['text'] = transcription.get('text', '')
    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        result['error'] = str(e)
    
    return result


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
        
        # Initialize embedding manager
        self.embedding_manager = SimpleEmbeddingManager('all-MiniLM-L6-v2')
        
        # Initialize vector store
        self.vector_store = SimpleVectorStore(
            dimension=self.embedding_manager.get_embedding_dimension()
        )
        
        # Initialize answer generator
        self.answer_generator = SimpleAnswerGenerator(
            min_confidence=app.config['SIMILARITY_THRESHOLD']
        )
        
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


# ============================================================================
# FILE PROCESSING
# ============================================================================

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
        
        if file_ext == 'pdf':
            logger.info(f"Processing PDF: {file_path}")
            documents = app_state.document_processor.load_document(file_path)
            
        elif file_ext == 'docx':
            logger.info(f"Processing DOCX: {file_path}")
            documents = app_state.document_processor.load_document(file_path)
            
        elif file_ext == 'txt':
            logger.info(f"Processing TXT: {file_path}")
            documents = app_state.document_processor.load_document(file_path)
            
        elif file_ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac']:
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
            chunks = app_state.document_processor.chunk_documents(documents)
            
            # Add metadata to chunks
            for i, chunk in enumerate(chunks):
                if not hasattr(chunk, 'metadata') or not chunk.metadata:
                    chunk.metadata = {}
                chunk.metadata['chunk_index'] = i
                chunk.metadata['document_id'] = file_id
                chunk.metadata['filename'] = filename
            
            # Generate embeddings
            embeddings = app_state.embedding_manager.embed_documents(chunks)
            metadatas = [c.metadata for c in chunks]
            
            # Add to vector store
            app_state.vector_store.add_documents(chunks, embeddings, metadatas)
            
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


# ============================================================================
# QUERY PROCESSING
# ============================================================================

def retrieve_and_answer(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Retrieve relevant documents and generate answer with citations."""
    result = {
        'success': False,
        'answer': '',
        'citations': [],
        'error': None
    }
    
    try:
        # Embed the query
        query_embedding = app_state.embedding_manager.embed_query(query)
        
        # Search vector store
        search_results = app_state.vector_store.similarity_search(
            query_embedding=query_embedding,
            k=max_results
        )
        
        if not search_results:
            result['answer'] = "No documents found. Please upload documents first."
            result['success'] = True
            return result
        
        # Prepare retrieved results
        retrieved_data = []
        for doc in search_results:
            score = doc.metadata.get('similarity_score', 0) if hasattr(doc, 'metadata') else 0
            retrieved_data.append({
                'content': doc.page_content if hasattr(doc, 'page_content') else str(doc),
                'metadata': doc.metadata if hasattr(doc, 'metadata') else {},
                'similarity_score': score
            })
        
        # Generate answer
        generated_answer = app_state.answer_generator.generate(
            query=query,
            retrieved_results=retrieved_data,
            total_documents=len(app_state.uploaded_files)
        )
        
        # Build citations
        citations = []
        for doc in search_results:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            page_num = metadata.get('page_number', metadata.get('page', 'N/A'))
            
            content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            verbatim = content[:300]
            if len(content) > 300:
                verbatim += "..."
            
            citation = {
                'source_file': metadata.get('filename', 'Unknown'),
                'page_number': page_num,
                'chunk_index': metadata.get('chunk_index', 0),
                'similarity_score': metadata.get('similarity_score', 0),
                'verbatim': verbatim,
                'full_text': content,
                'source_type': metadata.get('source_type', 'document'),
                'location': f"Page {page_num}, Chunk {metadata.get('chunk_index', 0) + 1}"
            }
            citations.append(citation)
        
        # Build answer text
        answer_text = generated_answer.answer_text
        
        if citations:
            answer_text += "\n\nSources:\n"
            for i, cite in enumerate(citations, 1):
                answer_text += f"[{i}] {cite['source_file']} ({cite['location']})\n"
                answer_text += f"    \"{cite['verbatim']}\"\n"
        
        result['success'] = True
        result['answer'] = answer_text
        result['citations'] = citations
        result['answer_type'] = generated_answer.answer_type
        result['confidence'] = generated_answer.confidence
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'rag_initialized': app_state.is_initialized,
        'files_uploaded': len(app_state.uploaded_files),
        'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
        'langchain': LANGCHAIN_AVAILABLE,
        'whisper': WHISPER_AVAILABLE
    })

@app.route('/api/initialize', methods=['POST'])
def initialize():
    """Initialize the RAG application."""
    try:
        if not app_state.is_initialized:
            app_state.initialize()
        
        return jsonify({
            'success': True,
            'message': 'RAG application initialized',
            'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
            'langchain': LANGCHAIN_AVAILABLE,
            'whisper': WHISPER_AVAILABLE
        })
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    try:
        # Initialize if needed
        if not app_state.is_initialized:
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
        result = process_uploaded_file(file_path, file_id)
        
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

@app.route('/api/query', methods=['POST'])
def query():
    """Handle query request."""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'error': 'No question provided'
            }), 400
        
        question = data['question'].strip()
        
        if not question:
            return jsonify({
                'success': False,
                'error': 'Empty question'
            }), 400
        
        if not app_state.uploaded_files:
            return jsonify({
                'success': False,
                'error': 'No documents uploaded. Please upload documents first.'
            }), 400
        
        max_results = data.get('max_results', 5)
        result = retrieve_and_answer(question, max_results=max_results)
        
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
                'filename': info['filename'],
                'file_type': info['file_type'].replace('.', ''),
                'chunks': info['chunks'],
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

@app.route('/api/image', methods=['GET'])
def answerimagequery():
    files = []
    for file_id, info in app_state.uploaded_files.items():
            files.append({
                'file_id': file_id,
                'filename': info['filename'],
                'file_type': info['file_type'].replace('.', ''),
                'chunks': info['chunks'],
                'upload_time': info['upload_time']
            })
   
    vs = VisionModel()
    full_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], 'butchCoug.jpg'))
    
    result = vs.GetSingleImgDesc(full_path)
    
    return jsonify({
        'message': result})


    # return jsonify("Test")
   


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Initialize on startup
    app_state.initialize()
    
    # Run Flask
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
