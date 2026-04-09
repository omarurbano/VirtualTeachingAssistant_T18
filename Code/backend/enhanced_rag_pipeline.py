"""
Multi-File RAG System - Enhanced RAG Pipeline with Multimodal Support
===================================================================

This module extends the RAG pipeline to support complex documents with:
- Multiple content types (text, tables, images with OCR)
- Page-level and region-level position tracking
- Enhanced citation system with location information
- Integration with the multimodal document processor

This handles PDFs with images, tables, captions, and OCR'd text.

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

# Import hashlib for generating unique IDs
import hashlib

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# TYPING IMPORTS
# ============================================================================

# Import typing for type hints
from typing import List, Dict, Optional, Any, Union, Tuple

# ============================================================================
# LOCAL MODULE IMPORTS
# ============================================================================

# Import our custom modules
from document_loader import (
    MultiFileLoader,
    DocumentMetadata,
    SUPPORTED_FILE_TYPES
)

from embedding_manager import (
    EmbeddingManager,
    create_embedding_manager
)

from vector_store import (
    MultiFileVectorStore,
    create_vector_store
)

from citation_tracker import (
    CitationTracker,
    CitationSource,
    CitationFormatter,
    format_inline_citations
)

# Import multimodal processor
try:
    from multimodal_processor import (
        MultimodalDocumentProcessor,
        MultimodalElement,
        extract_all_content,
        ELEMENT_TYPE_TEXT,
        ELEMENT_TYPE_TABLE,
        ELEMENT_TYPE_IMAGE,
        ELEMENT_TYPE_OCR
    )
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False
    logging.warning("Multimodal processor not available. Install dependencies for full support.")

# Import answer generator
try:
    from answer_generator import (
        AnswerGenerator,
        GeneratedAnswer,
        AnswerContext
    )
    ANSWER_GENERATOR_AVAILABLE = True
except ImportError:
    ANSWER_GENERATOR_AVAILABLE = False
    logging.warning("Answer generator not available.")

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
# ENHANCED CITATION CLASSES
# ============================================================================

class EnhancedCitationSource(CitationSource):
    """
    Enhanced citation source with multimodal position tracking.
    
    This extends the base CitationSource to include:
    - Page number
    - Region coordinates
    - Element type (text, table, image, OCR)
    - Caption information
    
    Attributes:
        page_number: Page number where element was found
        coordinates: Bounding box coordinates (x1, y1, x2, y2)
        element_type: Type of element (text, table, image, ocr)
        caption: Associated caption
    """
    
    def __init__(
        self,
        chunk_id: int,
        document_id: str,
        source_file: str,
        source_path: str,
        file_type: str,
        content: str,
        chunk_index: int = 0,
        char_start: int = 0,
        char_end: int = 0,
        similarity_score: float = 0.0,
        metadata: Dict = None,
        page_number: int = 1,
        coordinates: Tuple[int, int, int, int] = None,
        element_type: str = 'text',
        caption: str = None
    ):
        """
        Initialize EnhancedCitationSource with multimodal tracking.
        
        Args:
            chunk_id: Unique chunk identifier
            document_id: Parent document ID
            source_file: File name
            source_path: Full file path
            file_type: File extension
            content: Text content
            chunk_index: Position in document
            char_start: Character start position
            char_end: Character end position
            similarity_score: Relevance score
            metadata: Additional metadata
            page_number: Page number
            coordinates: Bounding box
            element_type: Type of content
            caption: Associated caption
        """
        # Call parent constructor
        super().__init__(
            chunk_id=chunk_id,
            document_id=document_id,
            source_file=source_file,
            source_path=source_path,
            file_type=file_type,
            content=content,
            chunk_index=chunk_index,
            char_start=char_start,
            char_end=char_end,
            similarity_score=similarity_score,
            metadata=metadata
        )
        
        # Additional multimodal fields
        self.page_number = page_number
        self.coordinates = coordinates or (0, 0, 0, 0)
        self.element_type = element_type
        self.caption = caption
    
    def get_location_string(self) -> str:
        """
        Get detailed location string including page and region.
        
        Returns:
            Detailed location string
        """
        # Build location
        location = f"Page {self.page_number}"
        
        # Add element type
        type_labels = {
            'text': 'Text',
            'table': 'Table',
            'image': 'Image',
            'ocr': 'OCR Text',
            'title': 'Title'
        }
        
        type_label = type_labels.get(self.element_type, self.element_type)
        location += f", {type_label}"
        
        # Add coordinates if available
        if self.coordinates and self.coordinates != (0, 0, 0, 0):
            location += f" (pos: {self.coordinates[0]}, {self.coordinates[1]})"
        
        # Add caption if available
        if self.caption:
            location += f", Caption: {self.caption[:20]}..."
        
        return location
    
    def get_detailed_citation(self, style: str = 'detailed') -> str:
        """
        Get detailed citation with all available information.
        
        Args:
            style: Citation style
            
        Returns:
            Detailed citation string
        """
        if style == 'detailed':
            lines = [
                f"Source: {self.source_file}",
                f"Location: {self.get_location_string()}",
                f"Relevance: {self.similarity_score:.3f}",
                f"Content: {self.content[:150]}..." if len(self.content) > 150 else f"Content: {self.content}"
            ]
            return "\n".join(lines)
        
        elif style == 'academic':
            return f"{self.source_file}, p. {self.page_number}"
        
        elif style == 'verbose':
            return f"[{self.element_type.upper()}] {self.source_file} (p. {self.page_number}) - {self.similarity_score:.2f}"
        
        else:
            return super().get_location_string()
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary with enhanced fields.
        
        Returns:
            Dictionary with all citation information
        """
        base_dict = super().to_dict()
        
        # Add enhanced fields
        base_dict.update({
            'page_number': self.page_number,
            'coordinates': self.coordinates,
            'element_type': self.element_type,
            'caption': self.caption,
            'detailed_location': self.get_location_string()
        })
        
        return base_dict


# ============================================================================
# ENHANCED RAG PIPELINE
# ============================================================================

class EnhancedRAGPipeline:
    """
    Enhanced RAG Pipeline with multimodal document support.
    
    This pipeline extends the base RAG pipeline to handle complex
    PDF documents with multiple content types. It integrates the
    multimodal document processor to extract:
    - Plain text
    - Tables with structure
    - Images with OCR text
    - Position information
    
    The pipeline maintains detailed citations showing exactly where
    each piece of information was found.
    
    Example:
        >>> pipeline = EnhancedRAGPipeline()
        >>> pipeline.add_multimodal_file("complex_document.pdf")
        >>> result = pipeline.query("What does Figure 3 show?")
        >>> print(result['citations'])  # Shows page, region, caption info
    """
    
    def __init__(
        self,
        embedding_provider: str = 'sentence-transformers',
        embedding_model: str = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 100,
        storage_type: str = 'in_memory',
        vector_dimension: int = 384,
        max_citations: int = 10,
        use_multimodal: bool = True
    ):
        """
        Initialize the Enhanced RAG Pipeline.
        
        Args:
            embedding_provider: Embedding provider
            embedding_model: Specific model name
            chunk_size: Text chunk size
            chunk_overlap: Chunk overlap
            storage_type: Vector storage type
            vector_dimension: Embedding dimension
            max_citations: Maximum citations
            use_multimodal: Whether to use multimodal processing
        """
        # Store configuration
        self.config = {
            'embedding_provider': embedding_provider,
            'embedding_model': embedding_model,
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap,
            'storage_type': storage_type,
            'vector_dimension': vector_dimension,
            'max_citations': max_citations,
            'use_multimodal': use_multimodal and MULTIMODAL_AVAILABLE
        }
        
        # Initialize base components
        self.document_loader = MultiFileLoader(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        self.embedding_manager = create_embedding_manager(
            provider=embedding_provider,
            model_name=embedding_model
        )
        
        self.vector_store = create_vector_store(
            storage_type=storage_type,
            dimension=self.embedding_manager.get_embedding_dimension()
        )
        
        self.citation_tracker = CitationTracker(max_citations=max_citations)
        
        # Initialize multimodal processor if available
        if use_multimodal and MULTIMODAL_AVAILABLE:
            self.multimodal_processor = MultimodalDocumentProcessor(
                extract_images=True,
                extract_tables=True,
                ocr_images=True
            )
            logger.info("Multimodal processor enabled")
        else:
            self.multimodal_processor = None
            if use_multimodal:
                logger.warning("Multimodal requested but not available - falling back to standard processing")
        
        # Pipeline state
        self.is_initialized = True
        self.document_count = 0
        
        # Statistics
        self.stats = {
            'documents_added': 0,
            'total_chunks': 0,
            'multimodal_elements': 0,
            'queries_executed': 0,
            'by_element_type': {}
        }
        
        logger.info("Enhanced RAG Pipeline initialized successfully")
        logger.info(f"  Multimodal support: {self.config['use_multimodal']}")
    
    def add_multimodal_file(self, file_path: str) -> Dict[str, Any]:
        """
        Add a file with multimodal processing.
        
        This method handles complex PDF files using the multimodal
        processor to extract text, tables, images with OCR, and
        maintain position information.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Adding multimodal file: {file_path}")
        
        # Check file type
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Determine if we should use multimodal processing
        use_multimodal = (
            self.config['use_multimodal'] and
            file_ext == '.pdf' and
            self.multimodal_processor is not None
        )
        
        if use_multimodal:
            return self._add_with_multimodal_processing(file_path)
        else:
            return self._add_standard(file_path)
    
    def _add_with_multimodal_processing(self, file_path: str) -> Dict[str, Any]:
        """
        Add file using multimodal processing.
        
        Args:
            file_path: Path to file
            
        Returns:
            Operation results
        """
        try:
            # Extract all content using multimodal processor
            logger.info("Using multimodal processing")
            
            result = extract_all_content(
                file_path,
                include_images=True,
                include_tables=True,
                include_ocr=True
            )
            
            elements = result['elements']
            documents = result['documents']
            stats = result['statistics']
            
            if not documents:
                return {
                    'success': False,
                    'error': 'No content extracted from file'
                }
            
            # Generate embeddings
            embedding_results = self.embedding_manager.embed_documents_with_metadata(documents)
            
            # Add to vector store
            self.vector_store.add_documents(
                documents=documents,
                embeddings=embedding_results['embeddings'],
                metadatas=embedding_results['metadatas']
            )
            
            # Update statistics
            self.document_count += 1
            self.stats['documents_added'] += 1
            self.stats['total_chunks'] += len(documents)
            self.stats['multimodal_elements'] += len(elements)
            
            # Track element types
            for el_type, count in stats.get('by_type', {}).items():
                self.stats['by_element_type'][el_type] = (
                    self.stats['by_element_type'].get(el_type, 0) + count
                )
            
            file_info = self.document_loader.get_file_info(file_path)
            
            result_dict = {
                'success': True,
                'file_name': file_info['filename'],
                'file_type': file_info['file_type'],
                'elements_extracted': len(elements),
                'chunks_created': len(documents),
                'element_types': stats.get('by_type', {}),
                'pages': list(stats.get('by_page', {}).keys()),
                'document_id': documents[0].metadata.get('document_id', 'unknown')
            }
            
            logger.info(f"Successfully added multimodal file: {result_dict['file_name']}")
            logger.info(f"  Elements: {result_dict['elements_extracted']} ({result_dict['element_types']})")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error in multimodal processing: {e}")
            # Fallback to standard processing
            logger.info("Falling back to standard processing")
            return self._add_standard(file_path)
    
    def _add_standard(self, file_path: str) -> Dict[str, Any]:
        """
        Add file using standard processing.
        
        Args:
            file_path: Path to file
            
        Returns:
            Operation results
        """
        # Use base loader
        chunks = self.document_loader.load_and_chunk_file(file_path)
        
        if not chunks:
            return {
                'success': False,
                'error': 'No content extracted from file'
            }
        
        # Generate embeddings
        embedding_results = self.embedding_manager.embed_documents_with_metadata(chunks)
        
        # Add to vector store
        self.vector_store.add_documents(
            documents=chunks,
            embeddings=embedding_results['embeddings'],
            metadatas=embedding_results['metadatas']
        )
        
        # Update statistics
        self.document_count += 1
        self.stats['documents_added'] += 1
        self.stats['total_chunks'] += len(chunks)
        
        file_info = self.document_loader.get_file_info(file_path)
        
        result = {
            'success': True,
            'file_name': file_info['filename'],
            'file_type': file_info['file_type'],
            'chunks_created': len(chunks),
            'document_id': chunks[0].metadata.get('document_id', 'unknown'),
            'processing_mode': 'standard'
        }
        
        logger.info(f"Added file with standard processing: {result['file_name']}")
        
        return result
    
    def add_file(self, file_path: str) -> Dict[str, Any]:
        """
        Add a file - auto-detects processing method.
        
        Args:
            file_path: Path to file
            
        Returns:
            Operation results
        """
        return self.add_multimodal_file(file_path)
    
    def add_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Add multiple files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Overall results
        """
        results = {
            'total_files': len(file_paths),
            'successful': 0,
            'failed': 0,
            'files': []
        }
        
        for file_path in file_paths:
            result = self.add_file(file_path)
            
            if result.get('success'):
                results['successful'] += 1
            else:
                results['failed'] += 1
            
            results['files'].append(result)
        
        return results
    
    def query(
        self,
        query_text: str,
        k: int = 4,
        filter_by_file: str = None,
        filter_by_type: str = None,
        filter_by_page: int = None,
        include_citations: bool = True,
        citation_style: str = 'detailed'
    ) -> Dict[str, Any]:
        """
        Query the pipeline with enhanced filtering.
        
        This method extends the base query to support:
        - Filtering by element type (text, table, image, ocr)
        - Filtering by page number
        - Enhanced citation styles
        
        Args:
            query_text: The query
            k: Number of results
            filter_by_file: Filter by file name
            filter_by_type: Filter by element type
            filter_by_page: Filter by page number
            include_citations: Include citations
            citation_style: Style for citations
            
        Returns:
            Query results with enhanced citations
        """
        logger.info(f"Query: '{query_text}' (k={k})")
        
        # Check if we have documents
        if self.vector_store.get_statistics()['total_chunks'] == 0:
            return {
                'success': False,
                'error': 'No documents in the index. Please add documents first.',
                'query': query_text,
                'results': [],
                'citations': []
            }
        
        try:
            # Clear previous citations
            self.citation_tracker.clear()
            
            # Build metadata filter
            filter_metadata = {}
            if filter_by_file:
                filter_metadata['filename'] = filter_by_file
            if filter_by_type:
                filter_metadata['element_type'] = filter_by_type
            if filter_by_page:
                filter_metadata['page_number'] = filter_by_page
            
            # Generate query embedding
            query_embedding = self.embedding_manager.embed_query(query_text)
            
            # Perform search
            search_results = self.vector_store.similarity_search(
                query_embedding=query_embedding,
                k=k,
                filter_metadata=filter_metadata if filter_metadata else None,
                include_scores=True
            )
            
            # Track enhanced citations
            for result in search_results:
                metadata = result['metadata']
                
                # Create enhanced citation
                citation = EnhancedCitationSource(
                    chunk_id=metadata.get('chunk_id', 0),
                    document_id=metadata.get('document_id', 'unknown'),
                    source_file=metadata.get('filename', 'unknown'),
                    source_path=metadata.get('source', 'unknown'),
                    file_type=metadata.get('file_type', 'unknown'),
                    content=result['content'],
                    chunk_index=metadata.get('chunk_index', 0),
                    similarity_score=result.get('similarity_score', 0.0),
                    metadata=metadata,
                    page_number=metadata.get('page_number', 1),
                    coordinates=metadata.get('coordinates'),
                    element_type=metadata.get('element_type', 'text'),
                    caption=metadata.get('caption')
                )
                
                self.citation_tracker.add_citation(citation)
            
            # Format citations
            citations_text = ""
            citations_list = []
            
            if include_citations:
                if citation_style == 'detailed':
                    citations_text = self._format_detailed_citations(
                        self.citation_tracker.get_citations()
                    )
                else:
                    citations_text = self.citation_tracker.format_citations(
                        style='numbered',
                        include_scores=True,
                        max_results=k
                    )
                
                citations_list = self.citation_tracker.get_citations_dict()
            
            # Update stats
            self.stats['queries_executed'] += 1
            
            # Build result
            result = {
                'success': True,
                'query': query_text,
                'num_results': len(search_results),
                'results': [
                    {
                        'content': r['content'],
                        'metadata': r['metadata'],
                        'similarity_score': r.get('similarity_score', 0.0)
                    }
                    for r in search_results
                ],
                'citations': citations_text,
                'citations_list': citations_list,
                'sources': self.citation_tracker.get_unique_files(),
                'filters_applied': {
                    'file': filter_by_file,
                    'type': filter_by_type,
                    'page': filter_by_page
                }
            }
            
            logger.info(f"Query returned {len(search_results)} results")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query_text,
                'results': [],
                'citations': []
            }
    
    def _format_detailed_citations(
        self,
        citations: List[CitationSource]
    ) -> str:
        """
        Format citations with detailed location information.
        
        Args:
            citations: List of citations
            
        Returns:
            Formatted citation string
        """
        if not citations:
            return "No sources available."
        
        lines = ["=" * 60]
        lines.append("CITATIONS WITH LOCATION INFORMATION")
        lines.append("=" * 60)
        
        for i, citation in enumerate(citations, 1):
            # Get enhanced properties if available
            page = getattr(citation, 'page_number', 1)
            el_type = getattr(citation, 'element_type', 'text')
            coords = getattr(citation, 'coordinates', None)
            caption = getattr(citation, 'caption', None)
            
            lines.append(f"\n[{i}] {citation.source_file}")
            lines.append(f"    Page: {page}")
            lines.append(f"    Type: {el_type}")
            
            if coords and coords != (0, 0, 0, 0):
                lines.append(f"    Position: ({coords[0]}, {coords[1]})")
            
            if caption:
                lines.append(f"    Caption: {caption}")
            
            lines.append(f"    Relevance: {citation.similarity_score:.3f}")
            
            # Content preview
            content = citation.content[:150]
            if len(citation.content) > 150:
                content += "..."
            lines.append(f"    Content: {content}")
        
        return "\n".join(lines)
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get enhanced system status.
        
        Returns:
            Status with multimodal information
        """
        base_status = super().get_system_status() if hasattr(super(), 'get_system_status') else {}
        
        vector_stats = self.vector_store.get_statistics()
        
        return {
            'is_initialized': self.is_initialized,
            'document_count': self.document_count,
            'config': self.config,
            'stats': self.stats,
            'vector_store': vector_stats,
            'multimodal_enabled': self.config['use_multimodal'],
            'multimodal_processor_available': self.multimodal_processor is not None,
            'element_type_breakdown': self.stats.get('by_element_type', {}),
            'supported_file_types': list(SUPPORTED_FILE_TYPES.keys())
        }
    
    def get_multimodal_stats(self) -> Dict[str, Any]:
        """
        Get detailed multimodal statistics.
        
        Returns:
            Statistics about extracted content
        """
        return {
            'total_elements': self.stats['multimodal_elements'],
            'by_type': self.stats.get('by_element_type', {}),
            'processing_mode': 'multimodal' if self.config['use_multimodal'] else 'standard'
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_enhanced_pipeline(
    embedding_provider: str = 'sentence-transformers',
    enable_multimodal: bool = True,
    **kwargs
) -> EnhancedRAGPipeline:
    """
    Factory function to create an enhanced RAG pipeline.
    
    Args:
        embedding_provider: Embedding provider
        enable_multimodal: Enable multimodal processing
        **kwargs: Additional arguments
        
    Returns:
        Configured EnhancedRAGPipeline
    """
    return EnhancedRAGPipeline(
        embedding_provider=embedding_provider,
        use_multimodal=enable_multimodal,
        **kwargs
    )


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution for testing.
    """
    print("=" * 60)
    print("Enhanced RAG Pipeline - Multimodal Test")
    print("=" * 60)
    
    # Create pipeline
    print("\n--- Creating Enhanced Pipeline ---")
    pipeline = create_enhanced_pipeline(
        embedding_provider='mock',
        enable_multimodal=False  # Disable for basic test
    )
    
    # Get status
    print("\n--- Pipeline Status ---")
    status = pipeline.get_system_status()
    print(f"Initialized: {status['is_initialized']}")
    print(f"Multimodal enabled: {status['multimodal_enabled']}")
    print(f"Processor available: {status['multimodal_processor_available']}")
    
    print("\n" + "=" * 60)
    print("Enhanced pipeline ready.")
    print("=" * 60)
