"""
Multi-File RAG System - Embedding Manager Module
================================================

This module handles the creation of embeddings for document chunks.
It supports multiple embedding providers including sentence-transformers
for local embeddings and OpenAI for cloud-based embeddings.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2026-02-20
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

# Import os for environment variable access
import os

# Import logging for structured logging
import logging

# Import typing for type hints
from typing import List, Dict, Optional, Any, Union

# Import numpy for vector operations
import numpy as np

# Import hashlib for generating unique IDs
import hashlib

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# THIRD-PARTY LIBRARY IMPORTS
# ============================================================================

# Try to import sentence-transformers for local embeddings
# This is the preferred method as it's free and runs locally
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("sentence-transformers not available. Install with: pip install sentence-transformers")

# Try to import OpenAI for cloud embeddings
try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available. Install with: pip install langchain-openai")

# Try to import LangChain embeddings base class
try:
    from langchain.embeddings.base import Embeddings
except ImportError:
    # Fallback for older LangChain versions
    from langchain.embeddings import Embeddings

# ============================================================================
# CONFIGURATION AND CONSTANTS
# ============================================================================

# Default embedding model configurations
# These models are chosen for their balance of quality and speed

# Sentence-transformers models (local, free)
SENTENCE_TRANSFORMER_MODELS = {
    'all-MiniLM-L6-v2': {
        'dimensions': 384,
        'description': 'Fast, good quality (default)',
        'max_seq_length': 256
    },
    'all-mpnet-base-v2': {
        'dimensions': 768,
        'description': 'Higher quality, slower',
        'max_seq_length': 384
    },
    'paraphrase-multilingual-MiniLM-L12-v2': {
        'dimensions': 384,
        'description': 'Multilingual support',
        'max_seq_length': 128
    }
}

# OpenAI embedding models (cloud-based)
OPENAI_EMBEDDING_MODELS = {
    'text-embedding-3-small': {
        'dimensions': 1536,
        'description': 'Latest OpenAI small model (cost-effective)'
    },
    'text-embedding-3-large': {
        'dimensions': 3072,
        'description': 'Latest OpenAI large model (highest quality)'
    },
    'text-embedding-ada-002': {
        'dimensions': 1536,
        'description': 'Legacy OpenAI model'
    }
}

# Default configuration
DEFAULT_EMBEDDING_PROVIDER = 'sentence-transformers'
DEFAULT_SENTENCE_TRANSFORMER_MODEL = 'all-MiniLM-L6-v2'

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
# EMBEDDING CLASSES
# ============================================================================

class MockEmbeddings(Embeddings):
    """
    Mock embeddings class for testing without actual embeddings.
    
    This class provides a fallback when no embedding provider is available.
    It generates deterministic embeddings based on hash functions,
    which is useful for development and testing but not production.
    
    Note: These embeddings have no semantic meaning and should only
    be used for testing purposes.
    """
    
    def __init__(self, dimensions: int = 384):
        """
        Initialize mock embeddings with specified dimensions.
        
        Args:
            dimensions: Number of dimensions for embedding vectors
        """
        self.dimensions = dimensions
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for text in texts:
            # Generate deterministic embeddings based on text hash
            words = text.lower().split()
            
            # Create embedding from word hashes
            vec = [hash(word) % 100 / 100.0 for word in set(words)]
            
            # Pad or truncate to desired dimensions
            while len(vec) < self.dimensions:
                vec.append(0.0)
            
            embeddings.append(vec[:self.dimensions])
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """
        return self.embed_documents([text])[0]


class SentenceTransformerEmbeddings:
    """
    Wrapper class for sentence-transformers library.
    
    This class provides a clean interface to the sentence-transformers
    library for generating high-quality local embeddings. It handles
    model loading, caching, and embedding generation.
    
    Attributes:
        model_name: Name of the sentence-transformer model
        model: The underlying SentenceTransformer model instance
        dimensions: Number of embedding dimensions
    """
    
    def __init__(
        self,
        model_name: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        device: str = None,
        cache_folder: str = None
    ):
        """
        Initialize sentence-transformer embeddings.
        
        Args:
            model_name: Name of the model to use (from SENTENCE_TRANSFORMER_MODELS)
            device: Device to use ('cpu', 'cuda', or 'mps'). Auto-detects if None
            cache_folder: Folder to cache downloaded models
            
        Raises:
            ImportError: If sentence-transformers is not installed
            ValueError: If the model name is not recognized
        """
        # Check if sentence-transformers is available
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        # Validate model name
        if model_name not in SENTENCE_TRANSFORMER_MODELS:
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Available models: {list(SENTENCE_TRANSFORMER_MODELS.keys())}"
            )
        
        self.model_name = model_name
        self.model_config = SENTENCE_TRANSFORMER_MODELS[model_name]
        self.dimensions = self.model_config['dimensions']
        
        # Determine device (auto-detect if not specified)
        if device is None:
            if os.name == 'nt':
                # Windows: typically CPU or CUDA
                device = 'cuda' if self._check_cuda_available() else 'cpu'
            else:
                # Unix-like: CPU, CUDA, or MPS (Apple Silicon)
                device = 'mps' if self._check_mps_available() else 'cuda' if self._check_cuda_available() else 'cpu'
        
        self.device = device
        
        # Load the model
        logger.info(f"Loading sentence-transformer model: {model_name} on {device}")
        
        try:
            self.model = SentenceTransformer(
                model_name,
                device=device,
                cache_folder=cache_folder
            )
            logger.info(f"Model loaded successfully. Dimensions: {self.dimensions}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    
    def _check_cuda_available(self) -> bool:
        """
        Check if CUDA (NVIDIA GPU) is available.
        
        Returns:
            True if CUDA is available, False otherwise
        """
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _check_mps_available(self) -> bool:
        """
        Check if MPS (Apple Silicon) is available.
        
        Returns:
            True if MPS is available, False otherwise
        """
        try:
            import torch
            return hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        except ImportError:
            return False
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.
        
        This method takes a list of text strings and generates
        embedding vectors for each one using the sentence-transformer model.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []
        
        try:
            # Generate embeddings using the model
            # batch_size can be adjusted based on available memory
            embeddings = self.model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Convert numpy arrays to lists for compatibility
            return [emb.tolist() for emb in embeddings]
            
        except Exception as e:
            logger.error(f"Error generating document embeddings: {str(e)}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        This is optimized for single-query use cases and may
        have different performance characteristics than batch processing.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector as a list of floats
        """
        try:
            # Generate embedding for single text
            embedding = self.model.encode(
                text,
                convert_to_numpy=True
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimensionality of embeddings produced by this model.
        
        Returns:
            Number of dimensions in each embedding vector
        """
        return self.dimensions


class OpenAIEmbeddingsWrapper:
    """
    Wrapper class for OpenAI embeddings API.
    
    This class provides access to OpenAI's embedding models
    through their API. Requires an OpenAI API key.
    
    Attributes:
        model_name: Name of the OpenAI embedding model
        dimensions: Number of embedding dimensions
    """
    
    def __init__(
        self,
        model_name: str = 'text-embedding-3-small',
        api_key: str = None,
        organization: str = None,
        base_url: str = None
    ):
        """
        Initialize OpenAI embeddings.
        
        Args:
            model_name: Name of the OpenAI model (from OPENAI_EMBEDDING_MODELS)
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var if None
            organization: OpenAI organization ID (optional)
            base_url: Custom API endpoint (for API-compatible services)
            
        Raises:
            ImportError: If langchain-openai is not installed
            ValueError: If API key is not provided
        """
        # Check if OpenAI is available
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "langchain-openai is not installed. "
                "Install with: pip install langchain-openai"
            )
        
        # Get API key from parameter or environment
        if api_key is None:
            api_key = os.environ.get('OPENAI_API_KEY')
        
        if api_key is None:
            raise ValueError(
                "OpenAI API key is required. "
                "Provide it as a parameter or set OPENAI_API_KEY environment variable."
            )
        
        # Validate model name
        if model_name not in OPENAI_EMBEDDING_MODELS:
            logger.warning(
                f"Unknown model: {model_name}. "
                f"Available models: {list(OPENAI_EMBEDDING_MODELS.keys())}"
            )
        
        self.model_name = model_name
        self.dimensions = OPENAI_EMBEDDING_MODELS.get(model_name, {}).get('dimensions', 1536)
        
        # Initialize the OpenAI embeddings client
        logger.info(f"Initializing OpenAI embeddings with model: {model_name}")
        
        try:
            self.embeddings = OpenAIEmbeddings(
                model=model_name,
                api_key=api_key,
                organization=organization,
                base_url=base_url
            )
            logger.info("OpenAI embeddings initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embeddings: {str(e)}")
            raise
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents using OpenAI API.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        try:
            return self.embeddings.embed_documents(texts)
        except Exception as e:
            logger.error(f"Error generating OpenAI document embeddings: {str(e)}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text using OpenAI API.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            logger.error(f"Error generating OpenAI query embedding: {str(e)}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimensionality of embeddings produced by this model.
        
        Returns:
            Number of dimensions in each embedding vector
        """
        return self.dimensions


# ============================================================================
# MAIN EMBEDDING MANAGER CLASS
# ============================================================================

class EmbeddingManager:
    """
    Main class for managing embeddings across multiple providers.
    
    This class provides a unified interface for creating embeddings
    using different providers (sentence-transformers, OpenAI, or mock).
    It handles provider initialization, fallback logic, and embedding
    generation with proper error handling.
    
    Example:
        >>> manager = EmbeddingManager(provider='sentence-transformers')
        >>> embeddings = manager.embed_documents(["text1", "text2"])
        >>> query_embedding = manager.embed_query("query text")
    """
    
    def __init__(
        self,
        provider: str = DEFAULT_EMBEDDING_PROVIDER,
        model_name: str = None,
        **kwargs
    ):
        """
        Initialize the EmbeddingManager with specified provider.
        
        Args:
            provider: Embedding provider ('sentence-transformers', 'openai', or 'mock')
            model_name: Model name specific to the provider
            **kwargs: Additional provider-specific arguments
        """
        self.provider = provider.lower()
        self.model = None
        self.dimensions = 0
        
        # Initialize the appropriate embedding model
        if self.provider == 'sentence-transformers':
            self._init_sentence_transformer(model_name or DEFAULT_SENTENCE_TRANSFORMER_MODEL)
            
        elif self.provider == 'openai':
            self._init_openai(model_name or 'text-embedding-3-small', **kwargs)
            
        elif self.provider == 'mock':
            self._init_mock(model_name or 384)
            
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Supported providers: sentence-transformers, openai, mock"
            )
        
        logger.info(f"EmbeddingManager initialized with provider: {self.provider}")
    
    def _init_sentence_transformer(self, model_name: str):
        """
        Initialize sentence-transformer embeddings.
        
        Args:
            model_name: Name of the model to use
        """
        try:
            # Create the sentence-transformer wrapper
            self.model = SentenceTransformerEmbeddings(model_name=model_name)
            self.dimensions = self.model.get_embedding_dimension()
            logger.info(f"Initialized sentence-transformer: {model_name}")
            
        except ImportError as e:
            logger.warning(f"sentence-transformers not available: {e}")
            logger.info("Falling back to mock embeddings")
            self._init_mock()
    
    def _init_openai(self, model_name: str, **kwargs):
        """
        Initialize OpenAI embeddings.
        
        Args:
            model_name: Name of the OpenAI model
            **kwargs: Additional arguments for OpenAIEmbeddingsWrapper
        """
        try:
            # Create the OpenAI wrapper
            self.model = OpenAIEmbeddingsWrapper(model_name=model_name, **kwargs)
            self.dimensions = self.model.get_embedding_dimension()
            logger.info(f"Initialized OpenAI embeddings: {model_name}")
            
        except (ImportError, ValueError) as e:
            logger.warning(f"OpenAI not available: {e}")
            logger.info("Falling back to mock embeddings")
            self._init_mock()
    
    def _init_mock(self, dimensions: int = 384):
        """
        Initialize mock embeddings for testing.
        
        Args:
            dimensions: Number of dimensions for mock embeddings
        """
        self.model = MockEmbeddings(dimensions=dimensions)
        self.dimensions = dimensions
        logger.warning("Using mock embeddings (for testing only)")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.
        
        This is the main method for batch embedding generation.
        It takes a list of text strings and returns their embeddings.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text)
        """
        if not texts:
            logger.warning("No texts provided for embedding")
            return []
        
        logger.info(f"Embedding {len(texts)} document(s) using {self.provider}")
        
        try:
            # Delegate to the underlying model
            embeddings = self.model.embed_documents(texts)
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error embedding documents: {str(e)}")
            raise
    
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a single query text.
        
        This method is optimized for single-query use cases.
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """
        if not text:
            logger.warning("Empty query provided")
            return []
        
        try:
            return self.model.embed_query(text)
            
        except Exception as e:
            logger.error(f"Error embedding query: {str(e)}")
            raise
    
    def embed_documents_with_metadata(
        self,
        documents: List[Any]
    ) -> Dict[str, Any]:
        """
        Generate embeddings for documents with their metadata.
        
        This method extracts text from LangChain Document objects
        and maintains the association with their metadata.
        
        Args:
            documents: List of LangChain Document objects with page_content and metadata
            
        Returns:
            Dictionary containing:
                - embeddings: List of embedding vectors
                - texts: Original text strings
                - metadatas: List of metadata dictionaries
        """
        if not documents:
            return {'embeddings': [], 'texts': [], 'metadatas': []}
        
        # Extract texts from documents
        texts = [doc.page_content for doc in documents]
        
        # Extract metadata from documents
        metadatas = [doc.metadata for doc in documents]
        
        # Generate embeddings
        embeddings = self.embed_documents(texts)
        
        return {
            'embeddings': embeddings,
            'texts': texts,
            'metadatas': metadatas
        }
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimensionality of embeddings produced by this manager.
        
        Returns:
            Number of dimensions in each embedding vector
        """
        return self.dimensions
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the current embedding provider.
        
        Returns:
            Dictionary with provider details
        """
        return {
            'provider': self.provider,
            'dimensions': self.dimensions,
            'model_name': getattr(self.model, 'model_name', None) if hasattr(self.model, 'model_name') else 'N/A'
        }


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_embedding_manager(
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
    **kwargs
) -> EmbeddingManager:
    """
    Factory function to create an EmbeddingManager.
    
    This is a convenience function that creates an EmbeddingManager
    with sensible defaults.
    
    Args:
        provider: Embedding provider to use
        **kwargs: Additional arguments for the provider
        
    Returns:
        Configured EmbeddingManager instance
    """
    return EmbeddingManager(provider=provider, **kwargs)


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution block for testing the embedding manager.
    """
    print("=" * 60)
    print("Multi-File RAG - Embedding Manager Test")
    print("=" * 60)
    
    # Test with sentence-transformers (if available)
    print("\n--- Testing sentence-transformers ---")
    try:
        manager = create_embedding_manager(provider='sentence-transformers')
        info = manager.get_provider_info()
        print(f"Provider: {info['provider']}")
        print(f"Model: {info['model_name']}")
        print(f"Dimensions: {info['dimensions']}")
        
        # Test embedding
        test_texts = ["Hello world", "This is a test document"]
        embeddings = manager.embed_documents(test_texts)
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Embedding dimension: {len(embeddings[0])}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with mock
    print("\n--- Testing mock embeddings ---")
    try:
        mock_manager = create_embedding_manager(provider='mock', model_name=384)
        info = mock_manager.get_provider_info()
        print(f"Provider: {info['provider']}")
        print(f"Dimensions: {info['dimensions']}")
        
        test_texts = ["Hello world", "This is a test document"]
        embeddings = mock_manager.embed_documents(test_texts)
        print(f"Generated {len(embeddings)} embeddings")
        
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("Embedding manager ready for use.")
    print("=" * 60)
