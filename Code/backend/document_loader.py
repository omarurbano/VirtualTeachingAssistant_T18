"""
Multi-File RAG System - Document Loader Module
=============================================

This module provides comprehensive document loading capabilities for multiple file types.
It supports: TXT, PDF, DOCX, HTML, and Markdown files with proper metadata extraction.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2026-02-20
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

# Import OS module for file system operations (path checking, file existence)
import os

# Import logging module for structured logging and debugging
import logging

# Import glob for file pattern matching
import glob

# Import mimetypes for file type detection
import mimetypes

# Import hashlib for generating unique document IDs
import hashlib

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# THIRD-PARTY LIBRARY IMPORTS
# ============================================================================

# LangChain document loaders for various file formats
from langchain_community.document_loaders import (
    TextLoader,           # For plain text files
    PyPDFLoader,          # For PDF documents
    Docx2txtLoader,       # For Microsoft Word documents
    UnstructuredHTMLLoader,  # For HTML files
    UnstructuredMarkdownLoader  # For Markdown files
)

# LangChain text splitter for chunking documents
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Supported file extensions mapping to loader classes and MIME types
# This dictionary defines all supported file types, their extensions,
# and the appropriate LangChain loader to use for each
SUPPORTED_FILE_TYPES = {
    '.txt': {
        'loader': TextLoader,
        'mime_type': 'text/plain',
        'description': 'Plain Text'
    },
    '.pdf': {
        'loader': PyPDFLoader,
        'mime_type': 'application/pdf',
        'description': 'Portable Document Format'
    },
    '.docx': {
        'loader': Docx2txtLoader,
        'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'description': 'Microsoft Word Document'
    },
    '.html': {
        'loader': UnstructuredHTMLLoader,
        'mime_type': 'text/html',
        'description': 'HTML Web Page'
    },
    '.htm': {
        'loader': UnstructuredHTMLLoader,
        'mime_type': 'text/html',
        'description': 'HTML Web Page'
    },
    '.md': {
        'loader': UnstructuredMarkdownLoader,
        'mime_type': 'text/markdown',
        'description': 'Markdown Document'
    },
    '.markdown': {
        'loader': UnstructuredMarkdownLoader,
        'mime_type': 'text/markdown',
        'description': 'Markdown Document'
    }
}

# Default chunking parameters for document processing
# These can be adjusted based on the use case and document characteristics
DEFAULT_CHUNK_SIZE = 1000       # Number of characters per chunk
DEFAULT_CHUNK_OVERLAP = 100     # Number of overlapping characters between chunks

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging for this module
# This allows for debugging and monitoring of document loading operations
logger = logging.getLogger(__name__)

# Set default logging level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============================================================================
# DATA CLASSES FOR DOCUMENT METADATA
# ============================================================================

class DocumentMetadata:
    """
    Data class representing metadata for a loaded document.
    
    This class stores all relevant information about the source document
    including file path, type, creation date, and processing information.
    
    Attributes:
        source (str): Full path to the source file
        filename (str): Name of the file without path
        file_type (str): File extension (e.g., '.txt', '.pdf')
        mime_type (str): MIME type of the file
        file_size (int): Size of the file in bytes
        created_date (datetime): File creation timestamp
        modified_date (datetime): File modification timestamp
        document_id (str): Unique identifier for the document
        chunk_count (int): Number of chunks the document was split into
    """
    
    def __init__(
        self,
        source: str,
        filename: str,
        file_type: str,
        mime_type: str,
        file_size: int,
        created_date: datetime,
        modified_date: datetime,
        document_id: str = None,
        chunk_count: int = 0
    ):
        """
        Initialize DocumentMetadata with file information.
        
        Args:
            source: Full path to the source file
            filename: Name of the file without path
            file_type: File extension including the dot
            mime_type: MIME type of the file
            file_size: Size of the file in bytes
            created_date: When the file was created
            modified_date: When the file was last modified
            document_id: Optional unique identifier (generated if not provided)
            chunk_count: Number of chunks after processing
        """
        # Store all the metadata fields
        self.source = source
        self.filename = filename
        self.file_type = file_type
        self.mime_type = mime_type
        self.file_size = file_size
        self.created_date = created_date
        self.modified_date = modified_date
        self.document_id = document_id or self._generate_document_id(source)
        self.chunk_count = chunk_count
    
    def _generate_document_id(self, source: str) -> str:
        """
        Generate a unique document ID based on file path and timestamp.
        
        Uses SHA256 hash of the file path combined with current timestamp
        to create a unique identifier that can be used for tracking.
        
        Args:
            source: File path to generate ID from
            
        Returns:
            Unique document ID string
        """
        # Combine source path with timestamp for uniqueness
        hash_input = f"{source}_{datetime.now().isoformat()}"
        
        # Create SHA256 hash (truncated to 16 characters for readability)
        document_id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        return document_id
    
    def to_dict(self) -> dict:
        """
        Convert metadata to dictionary for serialization.
        
        Returns:
            Dictionary representation of the metadata
        """
        return {
            'source': self.source,
            'filename': self.filename,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'document_id': self.document_id,
            'chunk_count': self.chunk_count
        }


class ChunkMetadata:
    """
    Data class representing metadata for a document chunk.
    
    This class tracks the location and context of each chunk within
    the original document, enabling precise citation generation.
    
    Attributes:
        chunk_id (int): Unique identifier for this chunk
        document_id (str): ID of the parent document
        source_file (str): Name of the source file
        source_path (str): Full path to the source file
        char_start (int): Starting character position in original document
        char_end (int): Ending character position in original document
        chunk_index (int): Index of this chunk in the document's chunk list
    """
    
    def __init__(
        self,
        chunk_id: int,
        document_id: str,
        source_file: str,
        source_path: str,
        char_start: int = 0,
        char_end: int = 0,
        chunk_index: int = 0
    ):
        """
        Initialize ChunkMetadata with position information.
        
        Args:
            chunk_id: Unique identifier for this chunk
            document_id: ID of the parent document this chunk belongs to
            source_file: Name of the source file
            source_path: Full path to the source file
            char_start: Starting character position in original document
            char_end: Ending character position in original document
            chunk_index: Position of this chunk in the document's chunk list
        """
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.source_file = source_file
        self.source_path = source_path
        self.char_start = char_start
        self.char_end = char_end
        self.chunk_index = chunk_index
    
    def to_dict(self) -> dict:
        """
        Convert chunk metadata to dictionary for serialization.
        
        Returns:
            Dictionary representation of the chunk metadata
        """
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'source_file': self.source_file,
            'source_path': self.source_path,
            'char_start': self.char_start,
            'char_end': self.char_end,
            'chunk_index': self.chunk_index
        }


# ============================================================================
# MAIN DOCUMENT LOADER CLASS
# ============================================================================

class MultiFileLoader:
    """
    Main class for loading and processing multiple file types.
    
    This class provides a unified interface for loading documents of various
    types, with automatic format detection, metadata extraction, and
    chunking capabilities. It handles the complexity of different file
    formats and provides consistent output for downstream processing.
    
    Example:
        >>> loader = MultiFileLoader()
        >>> documents = loader.load_file("document.pdf")
        >>> chunks = loader.chunk_documents(documents)
    """
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        encoding: str = 'utf-8'
    ):
        """
        Initialize the MultiFileLoader with configuration.
        
        Args:
            chunk_size: Maximum size of each text chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
            encoding: Text encoding to use (default: UTF-8)
        """
        # Store configuration parameters
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = encoding
        
        # Initialize the text splitter with configured parameters
        # This will be used to split documents into manageable chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        
        # Dictionary to store loaded documents by document ID
        self.documents = {}
        
        # Counter for generating unique chunk IDs
        self._chunk_counter = 0
        
        # Log initialization
        logger.info(f"MultiFileLoader initialized with chunk_size={chunk_size}, overlap={chunk_overlap}")
    
    def is_supported(self, file_path: str) -> bool:
        """
        Check if a file type is supported by this loader.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file type is supported, False otherwise
        """
        # Extract file extension (including the dot)
        _, extension = os.path.splitext(file_path)
        
        # Convert to lowercase for case-insensitive comparison
        extension = extension.lower()
        
        # Check if extension is in supported types
        return extension in SUPPORTED_FILE_TYPES
    
    def get_file_info(self, file_path: str) -> dict:
        """
        Get information about a file without loading its contents.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary containing file information
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file type is not supported
        """
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check if file type is supported
        if not self.is_supported(file_path):
            raise ValueError(f"Unsupported file type: {os.path.splitext(file_path)[1]}")
        
        # Get file statistics
        file_stat = os.stat(file_path)
        
        # Extract file extension
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        
        # Get file info from SUPPORTED_FILE_TYPES dictionary
        file_info = SUPPORTED_FILE_TYPES.get(extension, {})
        
        # Return comprehensive file information
        return {
            'filename': os.path.basename(file_path),
            'file_path': os.path.abspath(file_path),
            'file_type': extension,
            'mime_type': file_info.get('mime_type', 'application/octet-stream'),
            'description': file_info.get('description', 'Unknown'),
            'file_size': file_stat.st_size,
            'created_date': datetime.fromtimestamp(file_stat.st_ctime),
            'modified_date': datetime.fromtimestamp(file_stat.st_mtime),
            'is_supported': True
        }
    
    def load_file(self, file_path: str) -> list:
        """
        Load a single file and return its contents as document objects.
        
        This method automatically detects the file type and uses the
        appropriate LangChain loader to extract text content. It also
        extracts and stores metadata about the document.
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            List of langchain Document objects with metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file type is not supported
            Exception: If loading fails for any reason
        """
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file type is supported
        if not self.is_supported(file_path):
            logger.error(f"Unsupported file type: {os.path.splitext(file_path)[1]}")
            raise ValueError(f"Unsupported file type: {os.path.splitext(file_path)[1]}")
        
        # Get file extension and look up the appropriate loader
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        file_type_info = SUPPORTED_FILE_TYPES[extension]
        
        # Get the loader class for this file type
        loader_class = file_type_info['loader']
        
        logger.info(f"Loading file: {file_path} (type: {file_type_info['description']})")
        
        try:
            # Initialize the appropriate loader
            # Some loaders require encoding specification
            if extension == '.txt':
                loader = loader_class(file_path, encoding=self.encoding)
            else:
                loader = loader_class(file_path)
            
            # Load the document
            loaded_docs = loader.load()
            
            # Get file information for metadata
            file_info = self.get_file_info(file_path)
            
            # Create document metadata
            doc_metadata = DocumentMetadata(
                source=file_info['file_path'],
                filename=file_info['filename'],
                file_type=file_info['file_type'],
                mime_type=file_info['mime_type'],
                file_size=file_info['file_size'],
                created_date=file_info['created_date'],
                modified_date=file_info['modified_date']
            )
            
            # Add metadata to each document
            # LangChain Document objects have a 'metadata' attribute
            for doc in loaded_docs:
                # Add document-level metadata
                doc.metadata = {
                    'source': doc_metadata.source,
                    'filename': doc_metadata.filename,
                    'file_type': doc_metadata.file_type,
                    'mime_type': doc_metadata.mime_type,
                    'document_id': doc_metadata.document_id,
                    'file_size': doc_metadata.file_size,
                    'created_date': doc_metadata.created_date.isoformat(),
                    'modified_date': doc_metadata.modified_date.isoformat()
                }
            
            # Store documents in internal dictionary
            self.documents[doc_metadata.document_id] = {
                'metadata': doc_metadata,
                'documents': loaded_docs
            }
            
            logger.info(f"Successfully loaded {len(loaded_docs)} page(s) from {file_info['filename']}")
            
            return loaded_docs
            
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise
    
    def load_directory(
        self,
        directory_path: str,
        file_pattern: str = "*.*",
        recursive: bool = False
    ) -> dict:
        """
        Load all supported files from a directory.
        
        This method scans a directory for supported file types and
        loads them all, returning a dictionary organized by document ID.
        
        Args:
            directory_path: Path to the directory to scan
            file_pattern: Glob pattern for matching files (default: all files)
            recursive: Whether to scan subdirectories (default: False)
            
        Returns:
            Dictionary mapping document IDs to their documents and metadata
        """
        # Validate directory exists
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"Directory not found: {directory_path}")
        
        logger.info(f"Loading files from directory: {directory_path}")
        
        # Determine glob pattern based on recursive flag
        if recursive:
            # Recursive search with pattern
            search_pattern = os.path.join(directory_path, "**", file_pattern)
            files = glob.glob(search_pattern, recursive=True)
        else:
            # Non-recursive search with pattern
            search_pattern = os.path.join(directory_path, file_pattern)
            files = glob.glob(search_pattern)
        
        # Filter to only supported file types
        supported_files = [f for f in files if self.is_supported(f)]
        
        # Sort for consistent ordering
        supported_files.sort()
        
        logger.info(f"Found {len(supported_files)} supported files out of {len(files)} total")
        
        # Load each supported file
        results = {}
        errors = []
        
        for file_path in supported_files:
            try:
                # Load the file
                docs = self.load_file(file_path)
                
                # Get the document ID from the first page's metadata
                doc_id = docs[0].metadata.get('document_id')
                
                if doc_id:
                    results[doc_id] = {
                        'documents': docs,
                        'metadata': self.documents.get(doc_id, {}).get('metadata')
                    }
                    
            except Exception as e:
                # Log error but continue with other files
                logger.warning(f"Failed to load {file_path}: {str(e)}")
                errors.append({
                    'file': file_path,
                    'error': str(e)
                })
        
        # Log summary
        logger.info(f"Successfully loaded {len(results)} files, {len(errors)} failures")
        
        return results
    
    def chunk_documents(
        self,
        documents: list,
        add_chunk_metadata: bool = True
    ) -> list:
        """
        Split documents into smaller, overlapping chunks.
        
        This method takes loaded documents and splits them into chunks
        of specified size. Each chunk retains metadata about its
        source document and position within that document.
        
        Args:
            documents: List of LangChain Document objects to chunk
            add_chunk_metadata: Whether to add detailed chunk position metadata
            
        Returns:
            List of chunked documents with enhanced metadata
        """
        if not documents:
            logger.warning("No documents provided for chunking")
            return []
        
        logger.info(f"Chunking {len(documents)} document(s)")
        
        # Split documents using the text splitter
        chunked_docs = self.text_splitter.split_documents(documents)
        
        # Add chunk-specific metadata if requested
        if add_chunk_metadata:
            for i, chunk in enumerate(chunked_docs):
                # Generate unique chunk ID
                chunk_id = self._chunk_counter
                self._chunk_counter += 1
                
                # Extract source information from original document
                source_file = chunk.metadata.get('filename', 'unknown')
                source_path = chunk.metadata.get('source', 'unknown')
                document_id = chunk.metadata.get('document_id', 'unknown')
                
                # Add chunk-specific metadata
                chunk.metadata['chunk_id'] = chunk_id
                chunk.metadata['chunk_index'] = i
                chunk.metadata['total_chunks'] = len(chunked_docs)
                
                # Create chunk metadata object for citation tracking
                chunk_metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    source_file=source_file,
                    source_path=source_path,
                    chunk_index=i
                )
                
                # Store chunk metadata in the chunk's metadata dict
                chunk.metadata['chunk_metadata'] = chunk_metadata.to_dict()
        
        logger.info(f"Created {len(chunked_docs)} chunks from {len(documents)} document(s)")
        
        return chunked_docs
    
    def load_and_chunk_file(self, file_path: str) -> list:
        """
        Convenience method to load and chunk a file in one step.
        
        This combines load_file() and chunk_documents() into a single
        operation for common use cases.
        
        Args:
            file_path: Path to the file to load and chunk
            
        Returns:
            List of chunked documents ready for embedding
        """
        # Load the file
        documents = self.load_file(file_path)
        
        # Chunk the documents
        chunks = self.chunk_documents(documents)
        
        # Update document metadata with chunk count
        if documents and documents[0].metadata.get('document_id'):
            doc_id = documents[0].metadata['document_id']
            if doc_id in self.documents:
                self.documents[doc_id]['metadata'].chunk_count = len(chunks)
        
        return chunks
    
    def get_document_by_id(self, document_id: str) -> dict:
        """
        Retrieve a previously loaded document by its ID.
        
        Args:
            document_id: The unique identifier of the document
            
        Returns:
            Dictionary containing the document and its metadata, or None if not found
        """
        return self.documents.get(document_id)
    
    def get_all_document_ids(self) -> list:
        """
        Get list of all loaded document IDs.
        
        Returns:
            List of document ID strings
        """
        return list(self.documents.keys())
    
    def get_document_count(self) -> int:
        """
        Get the total number of loaded documents.
        
        Returns:
            Number of documents currently loaded
        """
        return len(self.documents)
    
    def clear_documents(self):
        """
        Clear all loaded documents from memory.
        
        This method resets the loader to its initial state,
        clearing all stored documents and resetting counters.
        """
        self.documents.clear()
        self._chunk_counter = 0
        logger.info("All documents cleared from memory")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_supported_extensions() -> list:
    """
    Get list of all supported file extensions.
    
    Returns:
        List of supported file extensions (with dots)
    """
    return list(SPPORTED_FILE_TYPES.keys())


def get_file_type_description(extension: str) -> str:
    """
    Get human-readable description for a file extension.
    
    Args:
        extension: File extension (with or without dot)
        
    Returns:
        Description of the file type, or 'Unknown' if not supported
    """
    # Ensure extension has a leading dot
    if not extension.startswith('.'):
        extension = '.' + extension
    
    extension = extension.lower()
    
    file_info = SUPPORTED_FILE_TYPES.get(extension, {})
    
    return file_info.get('description', 'Unknown')


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution block for testing the document loader.
    
    This demonstrates basic usage of the MultiFileLoader class.
    """
    # Print welcome message
    print("=" * 60)
    print("Multi-File RAG Document Loader - Test")
    print("=" * 60)
    
    # List supported file types
    print("\nSupported file types:")
    for ext in get_supported_extensions():
        desc = get_file_type_description(ext)
        print(f"  {ext}: {desc}")
    
    # Create loader instance
    loader = MultiFileLoader(chunk_size=500, chunk_overlap=50)
    
    print(f"\nLoader initialized with:")
    print(f"  Chunk size: {loader.chunk_size}")
    print(f"  Chunk overlap: {loader.chunk_overlap}")
    
    print("\n" + "=" * 60)
    print("Document loader ready for use.")
    print("=" * 60)
