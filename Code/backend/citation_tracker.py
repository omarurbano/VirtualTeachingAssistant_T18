"""
Multi-File RAG System - Citation Tracker Module
================================================

This module handles tracking and generating citations for retrieved
information. It maintains the connection between source documents,
chunks, and their positions, enabling accurate citation generation
in the RAG pipeline output.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2026-02-20
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

# Import os for file path operations
import os

# Import logging for structured logging
import logging

# Import json for serialization
import json

# Import hashlib for generating unique IDs
import hashlib

# Import re for text processing
import re

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# TYPING IMPORTS
# ============================================================================

# Import typing for type hints
from typing import List, Dict, Optional, Any, Tuple, Union

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
# CITATION FORMAT CLASSES
# ============================================================================

class CitationSource:
    """
    Represents a single source/citation for retrieved information.
    
    This class encapsulates all information needed to cite a specific
    chunk of content from a document, including file name, position,
    and relevance metrics.
    
    Attributes:
        chunk_id: Unique identifier for the chunk
        document_id: Unique identifier for the source document
        source_file: Name of the source file
        source_path: Full path to the source file
        file_type: Type/extension of the source file
        content: The actual text content of the chunk
        chunk_index: Position of this chunk in the document
        char_start: Starting character position in original document
        char_end: Ending character position in original document
        similarity_score: Relevance score from similarity search
        metadata: Additional metadata about the chunk
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
        metadata: Dict = None
    ):
        """
        Initialize a CitationSource with all relevant information.
        
        Args:
            chunk_id: Unique chunk identifier
            document_id: Parent document identifier
            source_file: File name
            source_path: Full file path
            file_type: File extension
            content: Text content
            chunk_index: Position in document
            char_start: Character start position
            char_end: Character end position
            similarity_score: Relevance score
            metadata: Additional metadata dict
        """
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.source_file = source_file
        self.source_path = source_path
        self.file_type = file_type
        self.content = content
        self.chunk_index = chunk_index
        self.char_start = char_start
        self.char_end = char_end
        self.similarity_score = similarity_score
        self.metadata = metadata or {}
    
    @classmethod
    def from_chunk(
        cls,
        chunk: Any,
        similarity_score: float = 0.0
    ) -> 'CitationSource':
        """
        Create a CitationSource from a LangChain document chunk.
        
        This factory method extracts all necessary information from
        a LangChain Document object to create a proper citation source.
        
        Args:
            chunk: LangChain Document object with page_content and metadata
            similarity_score: Relevance score from similarity search
            
        Returns:
            CitationSource instance
        """
        # Extract metadata with defaults
        metadata = chunk.metadata
        
        # Get chunk metadata if available (from our chunking process)
        chunk_metadata = metadata.get('chunk_metadata', {})
        
        return cls(
            chunk_id=metadata.get('chunk_id', chunk_metadata.get('chunk_id', 0)),
            document_id=metadata.get('document_id', 'unknown'),
            source_file=metadata.get('filename', 'unknown'),
            source_path=metadata.get('source', 'unknown'),
            file_type=metadata.get('file_type', '.txt'),
            content=chunk.page_content,
            chunk_index=metadata.get('chunk_index', chunk_metadata.get('chunk_index', 0)),
            char_start=chunk_metadata.get('char_start', 0),
            char_end=chunk_metadata.get('char_end', 0),
            similarity_score=similarity_score,
            metadata=metadata
        )
    
    def get_citation_id(self) -> str:
        """
        Generate a unique citation identifier.
        
        Returns:
            String identifier for this citation
        """
        # Create a unique ID based on document and chunk
        id_string = f"{self.document_id}_{self.chunk_id}"
        return hashlib.md5(id_string.encode()).hexdigest()[:8]
    
    def get_file_display_name(self) -> str:
        """
        Get a human-readable file name for display.
        
        Returns:
            File name without path, with type indicator if needed
        """
        # If multiple files have the same name, add type indicator
        base_name = os.path.splitext(self.source_file)[0]
        ext = os.path.splitext(self.source_file)[1]
        
        return f"{base_name}{ext}"
    
    def get_location_string(self) -> str:
        """
        Get a string describing the location in the source.
        
        Returns:
            Location string (e.g., "Section 2", "Page 3", "Chunk 5")
        """
        # Try to extract section/page info from metadata
        if 'page' in self.metadata:
            return f"Page {self.metadata['page']}"
        elif 'section' in self.metadata:
            return f"Section {self.metadata['section']}"
        else:
            return f"Chunk {self.chunk_index + 1}"
    
    def to_dict(self) -> Dict:
        """
        Convert citation to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            'citation_id': self.get_citation_id(),
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'source_file': self.source_file,
            'source_path': self.source_path,
            'file_type': self.file_type,
            'content': self.content,
            'chunk_index': self.chunk_index,
            'char_start': self.char_start,
            'char_end': self.char_end,
            'similarity_score': self.similarity_score,
            'location': self.get_location_string(),
            'metadata': self.metadata
        }


class CitationFormatter:
    """
    Formats citations in various styles for different use cases.
    
    This class provides methods to format citations in multiple
    standard formats including numbered, APA-style, and inline.
    
    Attributes:
        default_style: Default citation style to use
    """
    
    # Citation style constants
    STYLE_NUMBERED = 'numbered'
    STYLE_APA = 'apa'
    STYLE_INLINE = 'inline'
    STYLE_VERBATIM = 'verbatim'
    
    def __init__(self, default_style: str = STYLE_NUMBERED):
        """
        Initialize the CitationFormatter.
        
        Args:
            default_style: Default citation style
        """
        self.default_style = default_style
    
    def format_citation(
        self,
        source: CitationSource,
        style: str = None,
        include_score: bool = False,
        max_content_length: int = None
    ) -> str:
        """
        Format a single citation in the specified style.
        
        Args:
            source: CitationSource to format
            style: Citation style (uses default if None)
            include_score: Whether to include similarity score
            max_content_length: Max length of content preview
            
        Returns:
            Formatted citation string
        """
        style = style or self.default_style
        
        if style == self.STYLE_NUMBERED:
            return self._format_numbered(source, include_score)
        elif style == self.STYLE_APA:
            return self._format_apa(source, include_score)
        elif style == self.STYLE_INLINE:
            return self._format_inline(source, include_score)
        elif style == self.STYLE_VERBATIM:
            return self._format_verbatim(source, max_content_length)
        else:
            return self._format_numbered(source, include_score)
    
    def _format_numbered(
        self,
        source: CitationSource,
        include_score: bool
    ) -> str:
        """
        Format as numbered reference.
        
        Args:
            source: Source to format
            include_score: Whether to include score
            
        Returns:
            Numbered citation string
        """
        # Build the citation
        parts = [
            f"[{source.chunk_index + 1}] {source.get_file_display_name()}",
            f"({source.get_location_string()})"
        ]
        
        if include_score:
            parts.append(f"[Relevance: {source.similarity_score:.3f}]")
        
        # Add content preview
        content = source.content[:200]
        if len(source.content) > 200:
            content += "..."
        
        parts.append(f"\n{content}")
        
        return "\n".join(parts)
    
    def _format_apa(
        self,
        source: CitationSource,
        include_score: bool
    ) -> str:
        """
        Format as APA-style reference.
        
        Args:
            source: Source to format
            include_score: Whether to include score
            
        Returns:
            APA citation string
        """
        # Get file modification date if available
        modified = source.metadata.get('modified_date', 'n.d.')
        
        # Build APA citation
        citation = f"{source.get_file_display_name()} ({modified}). "
        citation += f"Retrieved from {source.source_path}. "
        citation += f"Location: {source.get_location_string()}."
        
        if include_score:
            citation += f" [Relevance: {source.similarity_score:.3f}]"
        
        return citation
    
    def _format_inline(
        self,
        source: CitationSource,
        include_score: bool
    ) -> str:
        """
        Format for inline citation.
        
        Args:
            source: Source to format
            include_score: Whether to include score
            
        Returns:
            Inline citation string
        """
        # Short inline citation like: (filename, chunk)
        score_str = f", {source.similarity_score:.2f}" if include_score else ""
        
        return f"({source.get_file_display_name()}, {source.get_location_string()}{score_str})"
    
    def _format_verbatim(
        self,
        source: CitationSource,
        max_length: int
    ) -> str:
        """
        Format as verbatim quote with citation.
        
        Args:
            source: Source to format
            max_length: Maximum content length
            
        Returns:
            Verbatim citation string
        """
        # Get content
        content = source.content
        
        # Truncate if needed
        if max_length and len(content) > max_length:
            content = content[:max_length] + "..."
        
        # Add source info
        formatted = f'"{content}"\n'
        formatted += f"  — {source.get_file_display_name()}, {source.get_location_string()}"
        
        return formatted
    
    def format_citations_list(
        self,
        sources: List[CitationSource],
        style: str = None,
        include_scores: bool = False
    ) -> str:
        """
        Format a list of citations.
        
        Args:
            sources: List of CitationSource objects
            style: Citation style
            include_scores: Whether to include similarity scores
            
        Returns:
            Formatted citations string
        """
        if not sources:
            return "No sources available."
        
        formatted_sources = []
        
        for i, source in enumerate(sources):
            # Add numbered prefix
            formatted = self.format_citation(
                source,
                style=style,
                include_score=include_scores
            )
            formatted_sources.append(formatted)
        
        return "\n\n".join(formatted_sources)


# ============================================================================
# MAIN CITATION TRACKER CLASS
# ============================================================================

class CitationTracker:
    """
    Tracks citations for retrieved documents in the RAG pipeline.
    
    This class maintains a registry of all citations generated during
    the retrieval process and provides methods to format and retrieve
    them for display. It also tracks which sources have been cited
    to avoid duplicates and ensure proper attribution.
    
    Example:
        >>> tracker = CitationTracker()
        >>> tracker.add_citation(source1, 0.95)
        >>> tracker.add_citation(source2, 0.87)
        >>> citations = tracker.get_citations()
    """
    
    def __init__(self, max_citations: int = 10):
        """
        Initialize the CitationTracker.
        
        Args:
            max_citations: Maximum number of citations to track
        """
        # Maximum citations to store
        self.max_citations = max_citations
        
        # List of all citations (CitationSource objects)
        self.citations = []
        
        # Dictionary to track unique sources (by document_id + chunk_id)
        self._source_index = {}
        
        # Citation formatter instance
        self.formatter = CitationFormatter()
        
        # Statistics
        self.stats = {
            'total_citations': 0,
            'unique_sources': 0,
            'citations_by_file': {}
        }
        
        logger.info(f"CitationTracker initialized with max_citations={max_citations}")
    
    def add_citation(
        self,
        source: Union[CitationSource, Any],
        similarity_score: float = 0.0
    ) -> CitationSource:
        """
        Add a citation to the tracker.
        
        This method accepts either a CitationSource object or a
        LangChain Document chunk and creates a citation from it.
        
        Args:
            source: CitationSource or LangChain Document chunk
            similarity_score: Relevance score from retrieval
            
        Returns:
            The created CitationSource
        """
        # Convert chunk to CitationSource if needed
        if not isinstance(source, CitationSource):
            source = CitationSource.from_chunk(source, similarity_score)
        
        # Check for duplicates
        source_key = f"{source.document_id}_{source.chunk_id}"
        
        if source_key in self._source_index:
            # Update existing citation with higher score if needed
            existing_idx = self._source_index[source_key]
            if source.similarity_score > self.citations[existing_idx].similarity_score:
                self.citations[existing_idx].similarity_score = source.similarity_score
            return self.citations[existing_idx]
        
        # Add to citations list
        self.citations.append(source)
        
        # Add to index
        self._source_index[source_key] = len(self.citations) - 1
        
        # Update statistics
        self._update_stats(source)
        
        # Trim if over max
        if len(self.citations) > self.max_citations:
            # Sort by score and keep top N
            self.citations.sort(key=lambda x: x.similarity_score, reverse=True)
            self._rebuild_index()
        
        logger.debug(f"Added citation: {source.get_citation_id()}")
        
        return source
    
    def add_citations(
        self,
        sources: List[Any],
        similarity_scores: List[float] = None
    ):
        """
        Add multiple citations at once.
        
        Args:
            sources: List of sources (CitationSource or chunks)
            similarity_scores: Optional list of similarity scores
        """
        if similarity_scores is None:
            similarity_scores = [0.0] * len(sources)
        
        for source, score in zip(sources, similarity_scores):
            self.add_citation(source, score)
    
    def _update_stats(self, source: CitationSource):
        """
        Update citation statistics.
        
        Args:
            source: CitationSource that was added
        """
        self.stats['total_citations'] += 1
        self.stats['unique_sources'] = len(self._source_index)
        
        # Track by file
        file_name = source.source_file
        if file_name not in self.stats['citations_by_file']:
            self.stats['citations_by_file'][file_name] = 0
        self.stats['citations_by_file'][file_name] += 1
    
    def _rebuild_index(self):
        """
        Rebuild the source index after trimming.
        """
        self._source_index = {}
        
        for idx, source in enumerate(self.citations):
            source_key = f"{source.document_id}_{source.chunk_id}"
            self._source_index[source_key] = idx
    
    def get_citations(
        self,
        max_results: int = None,
        min_score: float = None,
        sort_by_score: bool = True
    ) -> List[CitationSource]:
        """
        Get tracked citations with optional filtering.
        
        Args:
            max_results: Maximum number to return
            min_score: Minimum similarity score threshold
            sort_by_score: Whether to sort by score (descending)
            
        Returns:
            List of CitationSource objects
        """
        # Start with all citations
        results = list(self.citations)
        
        # Filter by minimum score
        if min_score is not None:
            results = [c for c in results if c.similarity_score >= min_score]
        
        # Sort by score if requested
        if sort_by_score:
            results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Limit results
        if max_results is not None:
            results = results[:max_results]
        
        return results
    
    def get_citation_by_index(self, index: int) -> Optional[CitationSource]:
        """
        Get a specific citation by its index.
        
        Args:
            index: Citation index
            
        Returns:
            CitationSource or None if not found
        """
        if 0 <= index < len(self.citations):
            return self.citations[index]
        return None
    
    def format_citations(
        self,
        style: str = CitationFormatter.STYLE_NUMBERED,
        include_scores: bool = True,
        max_results: int = None
    ) -> str:
        """
        Format all citations in the specified style.
        
        Args:
            style: Citation style to use
            include_scores: Whether to include similarity scores
            max_results: Maximum citations to format
            
        Returns:
            Formatted citations string
        """
        citations = self.get_citations(max_results=max_results)
        
        return self.formatter.format_citations_list(
            citations,
            style=style,
            include_scores=include_scores
        )
    
    def get_citations_dict(
        self,
        max_results: int = None
    ) -> List[Dict]:
        """
        Get citations as dictionaries.
        
        Args:
            max_results: Maximum citations to return
            
        Returns:
            List of citation dictionaries
        """
        citations = self.get_citations(max_results=max_results)
        
        return [c.to_dict() for c in citations]
    
    def get_statistics(self) -> Dict:
        """
        Get citation statistics.
        
        Returns:
            Dictionary of statistics
        """
        return {
            **self.stats,
            'current_citations': len(self.citations),
            'max_citations': self.max_citations
        }
    
    def get_unique_files(self) -> List[str]:
        """
        Get list of unique files that have been cited.
        
        Returns:
            List of file names
        """
        files = set()
        for citation in self.citations:
            files.add(citation.source_file)
        return sorted(list(files))
    
    def clear(self):
        """
        Clear all citations and reset statistics.
        """
        self.citations.clear()
        self._source_index.clear()
        self.stats = {
            'total_citations': 0,
            'unique_sources': 0,
            'citations_by_file': {}
        }
        logger.info("Citation tracker cleared")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_citation(
    chunk: Any,
    similarity_score: float = 0.0
) -> CitationSource:
    """
    Convenience function to create a citation from a chunk.
    
    Args:
        chunk: LangChain Document chunk
        similarity_score: Relevance score
        
    Returns:
        CitationSource instance
    """
    return CitationSource.from_chunk(chunk, similarity_score)


def format_inline_citations(
    citations: List[CitationSource]
) -> str:
    """
    Format multiple citations as inline references.
    
    Args:
        citations: List of CitationSource objects
        
    Returns:
        Inline citation string
    """
    if not citations:
        return ""
    
    # Extract unique file references
    refs = []
    for c in citations:
        ref = f"{c.get_file_display_name()}"
        if ref not in refs:
            refs.append(ref)
    
    # Format as: (file1, file2, file3)
    if len(refs) == 1:
        return f"({refs[0]})"
    elif len(refs) <= 3:
        return f"({', '.join(refs[:-1])}, and {refs[-1]})"
    else:
        return f"({', '.join(refs[:2])}, and {len(refs)-2} more)"


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution block for testing the citation tracker.
    """
    print("=" * 60)
    print("Multi-File RAG - Citation Tracker Test")
    print("=" * 60)
    
    # Create tracker
    tracker = CitationTracker(max_citations=5)
    
    # Create mock citation sources
    class MockChunk:
        def __init__(self, content, metadata):
            self.page_content = content
            self.metadata = metadata
    
    # Add some test citations
    chunks = [
        MockChunk(
            content="This is the first chunk about machine learning.",
            metadata={
                'chunk_id': 1,
                'document_id': 'doc1',
                'filename': 'ml_intro.txt',
                'source': '/data/ml_intro.txt',
                'file_type': '.txt',
                'chunk_index': 0
            }
        ),
        MockChunk(
            content="Deep learning uses neural networks with multiple layers.",
            metadata={
                'chunk_id': 2,
                'document_id': 'doc1',
                'filename': 'ml_intro.txt',
                'source': '/data/ml_intro.txt',
                'file_type': '.txt',
                'chunk_index': 1
            }
        ),
        MockChunk(
            content="Natural language processing deals with text data.",
            metadata={
                'chunk_id': 1,
                'document_id': 'doc2',
                'filename': 'nlp_guide.pdf',
                'source': '/data/nlp_guide.pdf',
                'file_type': '.pdf',
                'chunk_index': 0
            }
        )
    ]
    
    # Add citations with scores
    tracker.add_citation(chunks[0], 0.95)
    tracker.add_citation(chunks[1], 0.87)
    tracker.add_citation(chunks[2], 0.92)
    
    # Get formatted citations
    print("\n--- Numbered Citations ---")
    print(tracker.format_citations(style='numbered', include_scores=True))
    
    print("\n--- Inline Citations ---")
    print(format_inline_citations(tracker.get_citations()))
    
    # Get statistics
    print("\n--- Statistics ---")
    stats = tracker.get_statistics()
    print(f"Total citations: {stats['total_citations']}")
    print(f"Unique sources: {stats['unique_sources']}")
    print(f"Citations by file: {stats['citations_by_file']}")
    
    print("\n" + "=" * 60)
    print("Citation tracker ready for use.")
    print("=" * 60)
