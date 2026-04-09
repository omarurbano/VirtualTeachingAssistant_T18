"""
Multi-File RAG System - Vector Store Module
============================================

This module implements a vector store with comprehensive metadata
tracking. It stores document embeddings along with source information,
file types, and chunk positions, enabling proper citation generation
during retrieval.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2026-02-20
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

# Import os for file path operations
import os

# Import json for serialization
import json

# Import logging for structured logging
import logging

# Import pickle for in-memory storage serialization
import pickle

# Import hashlib for generating unique IDs
import hashlib

# Import shutil for file operations
import shutil

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# TYPING IMPORTS
# ============================================================================

# Import typing for type hints
from typing import List, Dict, Optional, Any, Tuple, Union, Callable

# Import numpy for vector operations
import numpy as np

# ============================================================================
# THIRD-PARTY LIBRARY IMPORTS
# ============================================================================

# Try to import ChromaDB for persistent vector storage
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB not available. Install with: pip install chromadb")

# Try to import LangChain vectorstore base classes
try:
    from langchain.schema import Document
except ImportError:
    # Define a simple fallback Document class
    class Document:
        """Fallback Document class when LangChain is not available."""
        def __init__(self, page_content: str = "", metadata: dict = None):
            self.page_content = page_content
            self.metadata = metadata or {}

# Try to import LangChain vectorstore base classes
try:
    from langchain.vectorstores import VectorStore
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("LangChain not available. Install with: pip install langchain")

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging for this module
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Storage type constants
STORAGE_IN_MEMORY = 'in_memory'
STORAGE_PERSISTENT = 'persistent'

# Default configuration
DEFAULT_STORAGE_TYPE = STORAGE_IN_MEMORY
DEFAULT_COLLECTION_NAME = 'multi_file_rag'
DEFAULT_PERSIST_DIRECTORY = './vector_store'

# Similarity metric constants
SIMILARITY_COSINE = 'cosine'
SIMILARITY_EUCLIDEAN = 'euclidean'
SIMILARITY_DOT_PRODUCT = 'dot_product'

# ============================================================================
# VECTOR STORE DATA STRUCTURES
# ============================================================================

class DocumentChunk:
    """
    Represents a document chunk with its embedding and metadata.
    
    This class combines the text content, embedding vector, and
    all necessary metadata for retrieval and citation purposes.
    
    Attributes:
        chunk_id: Unique identifier for this chunk
        document_id: ID of the parent document
        content: Text content of the chunk
        embedding: Vector embedding of the content
        metadata: Full metadata dictionary
        file_name: Source file name
        file_path: Full path to source file
        file_type: File extension
        char_start: Starting character position in original
        char_end: Ending character position in original
        chunk_index: Index of this chunk in the document
    """
    
    def __init__(
        self,
        chunk_id: int,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict,
        file_name: str = '',
        file_path: str = '',
        file_type: str = '',
        char_start: int = 0,
        char_end: int = 0,
        chunk_index: int = 0
    ):
        """
        Initialize a DocumentChunk.
        
        Args:
            chunk_id: Unique chunk identifier
            document_id: Parent document ID
            content: Text content
            embedding: Embedding vector
            metadata: Full metadata dictionary
            file_name: Source file name
            file_path: Source file path
            file_type: File extension
            char_start: Character start position
            char_end: Character end position
            chunk_index: Chunk position in document
        """
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.embedding = embedding
        self.metadata = metadata
        self.file_name = file_name
        self.file_path = file_path
        self.file_type = file_type
        self.char_start = char_start
        self.char_end = char_end
        self.chunk_index = chunk_index
    
    @classmethod
    def from_langchain_doc(
        cls,
        doc: Document,
        embedding: List[float],
        chunk_id: int
    ) -> 'DocumentChunk':
        """
        Create a DocumentChunk from a LangChain Document.
        
        Args:
            doc: LangChain Document object
            embedding: Embedding vector
            chunk_id: Unique chunk identifier
            
        Returns:
            DocumentChunk instance
        """
        # Extract metadata with defaults
        meta = doc.metadata
        
        return cls(
            chunk_id=chunk_id,
            document_id=meta.get('document_id', 'unknown'),
            content=doc.page_content,
            embedding=embedding,
            metadata=meta,
            file_name=meta.get('filename', ''),
            file_path=meta.get('source', ''),
            file_type=meta.get('file_type', ''),
            char_start=meta.get('chunk_metadata', {}).get('char_start', 0),
            char_end=meta.get('chunk_metadata', {}).get('char_end', 0),
            chunk_index=meta.get('chunk_index', 0)
        )
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'content': self.content,
            'embedding': self.embedding,
            'metadata': self.metadata,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'char_start': self.char_start,
            'char_end': self.char_end,
            'chunk_index': self.chunk_index
        }
    
    def to_langchain_doc(self) -> Document:
        """
        Convert back to LangChain Document.
        
        Returns:
            LangChain Document object
        """
        return Document(
            page_content=self.content,
            metadata=self.metadata
        )


# ============================================================================
# VECTOR STORE IMPLEMENTATIONS
# ============================================================================

class InMemoryVectorStore:
    """
    In-memory vector store implementation.
    
    This class provides a simple in-memory vector store that stores
    embeddings as numpy arrays and supports basic similarity search.
    It's suitable for small to medium-sized document collections.
    
    Attributes:
        chunks: List of DocumentChunk objects
        embeddings: Numpy array of all embeddings
        dimension: Embedding dimension
    """
    
    def __init__(self, dimension: int = 384):
        """
        Initialize the in-memory vector store.
        
        Args:
            dimension: Embedding vector dimension
        """
        # List to store document chunks
        self.chunks: List[DocumentChunk] = []
        
        # Numpy array for efficient vector operations
        self.embeddings: np.ndarray = None
        
        # Store dimension
        self.dimension = dimension
        
        # Chunk counter for unique IDs
        self._chunk_counter = 0
        
        # Metadata index for fast lookups
        self._metadata_index: Dict[str, List[int]] = {}
        
        logger.info(f"InMemoryVectorStore initialized with dimension={dimension}")
    
    def add_chunks(
        self,
        chunks: List[DocumentChunk]
    ):
        """
        Add multiple chunks to the store.
        
        Args:
            chunks: List of DocumentChunk objects
        """
        if not chunks:
            return
        
        # Add chunks to list
        for chunk in chunks:
            chunk.chunk_id = self._chunk_counter
            self._chunk_counter += 1
            self.chunks.append(chunk)
            
            # Update metadata index
            self._index_chunk_metadata(chunk)
        
        # Rebuild embeddings array
        self._rebuild_embeddings_array()
        
        logger.info(f"Added {len(chunks)} chunks to vector store (total: {len(self.chunks)})")
    
    def _index_chunk_metadata(self, chunk: DocumentChunk):
        """
        Index chunk metadata for fast filtering.
        
        Args:
            chunk: DocumentChunk to index
        """
        # Index by file name
        if chunk.file_name:
            if chunk.file_name not in self._metadata_index:
                self._metadata_index[chunk.file_name] = []
            self._metadata_index[chunk.file_name].append(len(self.chunks) - 1)
        
        # Index by document ID
        if chunk.document_id:
            doc_key = f"doc:{chunk.document_id}"
            if doc_key not in self._metadata_index:
                self._metadata_index[doc_key] = []
            self._metadata_index[doc_key].append(len(self.chunks) - 1)
        
        # Index by file type
        if chunk.file_type:
            type_key = f"type:{chunk.file_type}"
            if type_key not in self._metadata_index:
                self._metadata_index[type_key] = []
            self._metadata_index[type_key].append(len(self.chunks) - 1)
    
    def _rebuild_embeddings_array(self):
        """
        Rebuild the numpy embeddings array from chunks.
        """
        if not self.chunks:
            self.embeddings = np.array([])
            return
        
        # Stack embeddings into numpy array
        self.embeddings = np.array([c.embedding for c in self.chunks])
        
        # Update dimension
        if len(self.embeddings) > 0:
            self.dimension = len(self.embeddings[0])
    
    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 4,
        filter_metadata: Dict = None
    ) -> List[DocumentChunk]:
        """
        Perform similarity search on the vector store.
        
        This method finds the k most similar chunks to the query
        using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of most similar DocumentChunk objects
        """
        if not self.chunks or self.embeddings.size == 0:
            logger.warning("Vector store is empty")
            return []
        
        # Convert query to numpy array
        query = np.array(query_embedding)
        
        # Calculate cosine similarities
        # cos_sim = (A . B) / (||A|| * ||B||)
        query_norm = np.linalg.norm(query)
        
        if query_norm == 0:
            logger.warning("Query embedding has zero norm")
            return []
        
        # Calculate dot products with normalized vectors
        normalized_embeddings = self.embeddings / np.linalg.norm(
            self.embeddings,
            axis=1,
            keepdims=True
        )
        normalized_query = query / query_norm
        
        # Compute similarities
        similarities = np.dot(normalized_embeddings, normalized_query)
        
        # Get top k indices
        top_k_indices = np.argsort(similarities)[::-1][:k]
        
        # Filter by metadata if specified
        if filter_metadata:
            filtered_indices = []
            for idx in top_k_indices:
                chunk = self.chunks[idx]
                if self._matches_metadata(chunk, filter_metadata):
                    filtered_indices.append(idx)
            top_k_indices = filtered_indices[:k]
        
        # Build results
        results = []
        for idx in top_k_indices:
            if idx < len(self.chunks):
                chunk = self.chunks[idx]
                # Add similarity score to metadata
                chunk.metadata['similarity_score'] = float(similarities[idx])
                results.append(chunk)
        
        logger.debug(f"Similarity search returned {len(results)} results")
        
        return results
    
    def _matches_metadata(
        self,
        chunk: DocumentChunk,
        filter_dict: Dict
    ) -> bool:
        """
        Check if chunk metadata matches filter criteria.
        
        Args:
            chunk: DocumentChunk to check
            filter_dict: Filter criteria
            
        Returns:
            True if chunk matches all criteria
        """
        for key, value in filter_dict.items():
            chunk_value = chunk.metadata.get(key)
            
            # Handle special cases
            if key == 'file_name':
                chunk_value = chunk.file_name
            elif key == 'file_type':
                chunk_value = chunk.file_type
            elif key == 'document_id':
                chunk_value = chunk.document_id
            
            if chunk_value != value:
                return False
        
        return True
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[DocumentChunk]:
        """
        Get a specific chunk by its ID.
        
        Args:
            chunk_id: Chunk identifier
            
        Returns:
            DocumentChunk or None
        """
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None
    
    def get_chunks_by_file(self, file_name: str) -> List[DocumentChunk]:
        """
        Get all chunks from a specific file.
        
        Args:
            file_name: Name of the file
            
        Returns:
            List of DocumentChunk objects
        """
        return [c for c in self.chunks if c.file_name == file_name]
    
    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """
        Get all chunks from a specific document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of DocumentChunk objects
        """
        return [c for c in self.chunks if c.document_id == document_id]
    
    def get_chunk_count(self) -> int:
        """
        Get the total number of chunks in the store.
        
        Returns:
            Number of chunks
        """
        return len(self.chunks)
    
    def get_unique_files(self) -> List[str]:
        """
        Get list of unique file names in the store.
        
        Returns:
            List of file names
        """
        files = set()
        for chunk in self.chunks:
            if chunk.file_name:
                files.add(chunk.file_name)
        return sorted(list(files))
    
    def get_file_type_counts(self) -> Dict[str, int]:
        """
        Get count of chunks by file type.
        
        Returns:
            Dictionary mapping file types to counts
        """
        counts = {}
        for chunk in self.chunks:
            ft = chunk.file_type or 'unknown'
            counts[ft] = counts.get(ft, 0) + 1
        return counts
    
    def save(self, filepath: str):
        """
        Save the vector store to a file.
        
        Args:
            filepath: Path to save to
        """
        # Create directory if needed
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        
        # Save chunks as pickle
        with open(filepath, 'wb') as f:
            pickle.dump(self.chunks, f)
        
        logger.info(f"Vector store saved to {filepath}")
    
    def load(self, filepath: str):
        """
        Load the vector store from a file.
        
        Args:
            filepath: Path to load from
        """
        # Load chunks
        with open(filepath, 'rb') as f:
            self.chunks = pickle.load(f)
        
        # Rebuild embeddings array
        self._rebuild_embeddings_array()
        
        # Rebuild metadata index
        self._metadata_index = {}
        for chunk in self.chunks:
            self._index_chunk_metadata(chunk)
        
        logger.info(f"Vector store loaded from {filepath}")
    
    def clear(self):
        """
        Clear all chunks from the store.
        """
        self.chunks.clear()
        self.embeddings = np.array([])
        self._metadata_index.clear()
        self._chunk_counter = 0
        
        logger.info("Vector store cleared")


# ============================================================================
# MAIN VECTOR STORE WRAPPER CLASS
# ============================================================================

class MultiFileVectorStore:
    """
    Unified vector store interface supporting multiple backends.
    
    This class provides a consistent interface for vector storage
    regardless of the underlying implementation. It supports both
    in-memory and persistent storage with metadata filtering.
    
    Example:
        >>> store = MultiFileVectorStore(dimension=384)
        >>> store.add_documents(chunks, embeddings)
        >>> results = store.similarity_search(query_embedding, k=5)
    """
    
    def __init__(
        self,
        storage_type: str = DEFAULT_STORAGE_TYPE,
        dimension: int = 384,
        persist_directory: str = DEFAULT_PERSIST_DIRECTORY,
        collection_name: str = DEFAULT_COLLECTION_NAME
    ):
        """
        Initialize the vector store.
        
        Args:
            storage_type: Storage type ('in_memory' or 'persistent')
            dimension: Embedding dimension
            persist_directory: Directory for persistent storage
            collection_name: Name of the collection
        """
        self.storage_type = storage_type
        self.dimension = dimension
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # Initialize the appropriate backend
        if storage_type == STORAGE_IN_MEMORY:
            self._store = InMemoryVectorStore(dimension=dimension)
        elif storage_type == STORAGE_PERSISTENT and CHROMADB_AVAILABLE:
            self._init_chromadb()
        else:
            logger.warning(f"Storage type {storage_type} not available, using in-memory")
            self._store = InMemoryVectorStore(dimension=dimension)
        
        logger.info(f"MultiFileVectorStore initialized: {storage_type}")
    
    def _init_chromadb(self):
        """
        Initialize ChromaDB persistent storage.
        """
        try:
            # Create persistent client
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False
                )
            )
            
            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"dimension": self.dimension}
            )
            
            self._store = None  # ChromaDB handles storage
            
            logger.info(f"ChromaDB collection created: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            logger.warning("Falling back to in-memory storage")
            self._store = InMemoryVectorStore(dimension=self.dimension)
    
    def add_documents(
        self,
        documents: List[Any],
        embeddings: List[List[float]],
        metadatas: List[Dict] = None
    ):
        """
        Add documents with embeddings to the store.
        
        This method accepts LangChain Documents or our DocumentChunk
        objects and stores them with their embeddings.
        
        Args:
            documents: List of Document objects
            embeddings: List of embedding vectors
            metadatas: Optional list of metadata dictionaries
        """
        if not documents or not embeddings:
            logger.warning("No documents or embeddings provided")
            return
        
        if len(documents) != len(embeddings):
            raise ValueError(
                f"Number of documents ({len(documents)}) must match "
                f"number of embeddings ({len(embeddings)})"
            )
        
        if self.storage_type == STORAGE_PERSISTENT and CHROMADB_AVAILABLE:
            # Add to ChromaDB
            self._add_to_chromadb(documents, embeddings, metadatas)
        else:
            # Add to in-memory store
            self._add_to_memory(documents, embeddings, metadatas)
    
    def _add_to_memory(
        self,
        documents: List[Any],
        embeddings: List[List[float]],
        metadatas: List[Dict]
    ):
        """
        Add documents to in-memory store.
        
        Args:
            documents: List of documents
            embeddings: List of embeddings
            metadatas: List of metadata
        """
        # Convert to DocumentChunk objects
        chunks = []
        
        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            # Extract metadata
            meta = metadatas[i] if metadatas else {}
            
            # Handle LangChain Document or our chunk
            if hasattr(doc, 'page_content'):
                content = doc.page_content
                doc_meta = doc.metadata
            else:
                content = doc.content
                doc_meta = doc.metadata
            
            # Merge metadata
            full_meta = {**doc_meta, **meta}
            
            # Create chunk
            chunk = DocumentChunk(
                chunk_id=i,
                document_id=full_meta.get('document_id', 'unknown'),
                content=content,
                embedding=emb,
                metadata=full_meta,
                file_name=full_meta.get('filename', ''),
                file_path=full_meta.get('source', ''),
                file_type=full_meta.get('file_type', ''),
                chunk_index=full_meta.get('chunk_index', i)
            )
            
            chunks.append(chunk)
        
        # Add to store
        self._store.add_chunks(chunks)
        
        logger.info(f"Added {len(chunks)} documents to in-memory store")
    
    def _add_to_chromadb(
        self,
        documents: List[Any],
        embeddings: List[List[float]],
        metadatas: List[Dict]
    ):
        """
        Add documents to ChromaDB.
        
        Args:
            documents: List of documents
            embeddings: List of embeddings
            metadatas: List of metadata
        """
        # Prepare data for ChromaDB
        ids = [f"chunk_{i}" for i in range(len(documents))]
        
        # Extract contents
        contents = []
        for doc in documents:
            if hasattr(doc, 'page_content'):
                contents.append(doc.page_content)
            else:
                contents.append(doc.content)
        
        # Use provided metadatas or extract from documents
        if metadatas is None:
            metadatas = []
            for doc in documents:
                if hasattr(doc, 'metadata'):
                    metadatas.append(doc.metadata)
                else:
                    metadatas.append({})
        
        # Add to collection
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to ChromaDB")
    
    def similarity_search(
        self,
        query_embedding: List[float],
        k: int = 4,
        filter_metadata: Dict = None,
        include_scores: bool = True
    ) -> List[Dict]:
        """
        Perform similarity search.
        
        Args:
            query_embedding: Query embedding
            k: Number of results
            filter_metadata: Metadata filter
            include_scores: Include similarity scores
            
        Returns:
            List of result dictionaries with content and metadata
        """
        if self.storage_type == STORAGE_PERSISTENT and CHROMADB_AVAILABLE:
            return self._chromadb_search(query_embedding, k, filter_metadata)
        else:
            return self._memory_search(query_embedding, k, filter_metadata, include_scores)
    
    def _memory_search(
        self,
        query_embedding: List[float],
        k: int,
        filter_metadata: Dict,
        include_scores: bool
    ) -> List[Dict]:
        """
        Search in-memory store.
        
        Args:
            query_embedding: Query embedding
            k: Number of results
            filter_metadata: Metadata filter
            include_scores: Include scores
            
        Returns:
            List of result dictionaries
        """
        # Perform search
        chunks = self._store.similarity_search(
            query_embedding,
            k=k,
            filter_metadata=filter_metadata
        )
        
        # Convert to result dicts
        results = []
        for chunk in chunks:
            result = {
                'content': chunk.content,
                'metadata': chunk.metadata
            }
            
            if include_scores:
                result['similarity_score'] = chunk.metadata.get('similarity_score', 0.0)
            
            results.append(result)
        
        return results
    
    def _chromadb_search(
        self,
        query_embedding: List[float],
        k: int,
        filter_metadata: Dict
    ) -> List[Dict]:
        """
        Search ChromaDB.
        
        Args:
            query_embedding: Query embedding
            k: Number of results
            filter_metadata: Metadata filter
            
        Returns:
            List of result dictionaries
        """
        # Perform query
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_metadata
        )
        
        # Convert to our format
        output = []
        
        if results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                output.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'similarity_score': 1.0 - (results['distances'][0][i] if results.get('distances') else 0.0)
                })
        
        return output
    
    def get_statistics(self) -> Dict:
        """
        Get vector store statistics.
        
        Returns:
            Dictionary of statistics
        """
        if self.storage_type == STORAGE_PERSISTENT and CHROMADB_AVAILABLE:
            return {
                'storage_type': self.storage_type,
                'collection_name': self.collection_name,
                'total_chunks': self._collection.count(),
                'dimension': self.dimension
            }
        else:
            return {
                'storage_type': self.storage_type,
                'total_chunks': self._store.get_chunk_count(),
                'unique_files': self._store.get_unique_files(),
                'file_type_counts': self._store.get_file_type_counts(),
                'dimension': self.dimension
            }
    
    def clear(self):
        """
        Clear all data from the store.
        """
        if self.storage_type == STORAGE_PERSISTENT and CHROMADB_AVAILABLE:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"dimension": self.dimension}
            )
        else:
            self._store.clear()
        
        logger.info("Vector store cleared")


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_vector_store(
    storage_type: str = DEFAULT_STORAGE_TYPE,
    dimension: int = 384,
    **kwargs
) -> MultiFileVectorStore:
    """
    Factory function to create a vector store.
    
    Args:
        storage_type: Type of storage
        dimension: Embedding dimension
        **kwargs: Additional arguments
        
    Returns:
        Configured MultiFileVectorStore instance
    """
    return MultiFileVectorStore(
        storage_type=storage_type,
        dimension=dimension,
        **kwargs
    )


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution block for testing the vector store.
    """
    print("=" * 60)
    print("Multi-File RAG - Vector Store Test")
    print("=" * 60)
    
    # Create in-memory vector store
    store = create_vector_store(storage_type='in_memory', dimension=384)
    
    # Create test documents
    test_docs = [
        Document(
            page_content="Machine learning is a subset of artificial intelligence.",
            metadata={'document_id': 'doc1', 'filename': 'ml.txt', 'file_type': '.txt', 'chunk_index': 0}
        ),
        Document(
            page_content="Deep learning uses neural networks with multiple layers.",
            metadata={'document_id': 'doc1', 'filename': 'ml.txt', 'file_type': '.txt', 'chunk_index': 1}
        ),
        Document(
            page_content="Natural language processing deals with text and speech.",
            metadata={'document_id': 'doc2', 'filename': 'nlp.txt', 'file_type': '.txt', 'chunk_index': 0}
        )
    ]
    
    # Create test embeddings
    test_embeddings = [
        [0.1] * 384,
        [0.2] * 384,
        [0.3] * 384
    ]
    
    # Add documents
    print("\n--- Adding Documents ---")
    store.add_documents(test_docs, test_embeddings)
    
    # Get statistics
    print("\n--- Statistics ---")
    stats = store.get_statistics()
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Unique files: {stats['unique_files']}")
    print(f"File type counts: {stats['file_type_counts']}")
    
    # Perform search
    print("\n--- Similarity Search ---")
    query_embedding = [0.15] * 384
    results = store.similarity_search(query_embedding, k=2)
    
    for i, result in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Content: {result['content'][:50]}...")
        print(f"  Score: {result.get('similarity_score', 'N/A')}")
        print(f"  File: {result['metadata'].get('filename', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("Vector store ready for use.")
    print("=" * 60)
