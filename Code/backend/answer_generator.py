"""
Multi-File RAG System - Answer Generator Module
==============================================

This module handles generating answers from retrieved context with:
- Proper citation of sources
- Reasoning transparency
- Honest handling when information is not found in documents
- Fallback responses for out-of-scope queries

This ensures the system is honest about what it knows from the documents
versus what it doesn't know.

Author: CPT_S 421 Development Team
Version: 1.1.0
Created: 2026-02-22
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

# Import re for text processing
import re

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

# Import citation tracking
from citation_tracker import CitationSource

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
# CONSTANTS
# ============================================================================

# Confidence thresholds
HIGH_CONFIDENCE = 0.7    # Strong match found
MEDIUM_CONFIDENCE = 0.4  # Somewhat relevant
LOW_CONFIDENCE = 0.2     # Weak match, may not be relevant

# Answer types
ANSWER_TYPE_FOUND = 'found'                    # Information found in documents
ANSWER_TYPE_NOT_FOUND = 'not_found'           # Information not in documents
ANSWER_TYPE_PARTIAL = 'partial'               # Some information found, some missing
ANSWER_TYPE_AMBIGUOUS = 'ambiguous'          # Multiple possible answers

# ============================================================================
# DATA CLASSES
# ============================================================================

class AnswerContext:
    """
    Represents the context retrieved for answering a question.
    
    This class holds the raw retrieved chunks and their relevance
    scores, which are used to generate an answer.
    
    Attributes:
        query: The user's question
        retrieved_chunks: List of retrieved context chunks
        relevance_scores: List of similarity scores
        source_files: Unique source files
        total_chunks: Total chunks searched
    """
    
    def __init__(
        self,
        query: str,
        retrieved_chunks: List[Dict] = None,
        relevance_scores: List[float] = None,
        source_files: List[str] = None,
        total_chunks: int = 0
    ):
        """
        Initialize AnswerContext.
        
        Args:
            query: User's question
            retrieved_chunks: Retrieved context chunks
            relevance_scores: Similarity scores
            source_files: Source file names
            total_chunks: Total chunks in index
        """
        self.query = query
        self.retrieved_chunks = retrieved_chunks or []
        self.relevance_scores = relevance_scores or []
        self.source_files = source_files or []
        self.total_chunks = total_chunks
        
        # Calculate statistics
        self.max_score = max(relevance_scores) if relevance_scores else 0.0
        self.avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    def has_relevant_content(self, threshold: float = LOW_CONFIDENCE) -> bool:
        """
        Check if there is relevant content above threshold.
        
        Args:
            threshold: Minimum relevance score
            
        Returns:
            True if relevant content exists
        """
        return any(score >= threshold for score in self.relevance_scores)
    
    def get_best_score(self) -> float:
        """Get the highest relevance score."""
        return self.max_score
    
    def get_answer_confidence(self) -> str:
        """
        Determine confidence level of having answer.
        
        Returns:
            Confidence level string
        """
        if self.max_score >= HIGH_CONFIDENCE:
            return "high"
        elif self.max_score >= MEDIUM_CONFIDENCE:
            return "medium"
        elif self.max_score >= LOW_CONFIDENCE:
            return "low"
        else:
            return "none"


class GeneratedAnswer:
    """
    Represents a generated answer with full context.
    
    This class encapsulates:
    - The answer text
    - Reasoning explanation
    - Citations
    - Confidence level
    - Answer type (found/not found/partial)
    
    Attributes:
        answer_type: Type of answer (found/not_found/partial/ambiguous)
        answer_text: The generated answer
        reasoning: Explanation of how answer was derived
        citations: List of citation sources
        confidence: Confidence level (high/medium/low/none)
        context_used: Whether document context was used
    """
    
    def __init__(
        self,
        answer_type: str,
        answer_text: str,
        reasoning: str = "",
        citations: List[CitationSource] = None,
        confidence: str = "none",
        context_used: bool = False
    ):
        """
        Initialize GeneratedAnswer.
        
        Args:
            answer_type: Type of answer
            answer_text: The answer text
            reasoning: How answer was derived
            citations: Source citations
            confidence: Confidence level
            context_used: Whether document context was used
        """
        self.answer_type = answer_type
        self.answer_text = answer_text
        self.reasoning = reasoning
        self.citations = citations or []
        self.confidence = confidence
        self.context_used = context_used
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'answer_type': self.answer_type,
            'answer_text': self.answer_text,
            'reasoning': self.reasoning,
            'citations': [c.to_dict() for c in self.citations],
            'confidence': self.confidence,
            'context_used': self.context_used
        }
    
    def format_for_display(self, style: str = 'detailed') -> str:
        """
        Format answer for display.
        
        Args:
            style: Display style (detailed/simple/short)
            
        Returns:
            Formatted answer string
        """
        lines = []
        
        if style == 'detailed':
            lines.append("=" * 60)
            lines.append("ANSWER")
            lines.append("=" * 60)
            
            # Answer type indicator
            type_icons = {
                ANSWER_TYPE_FOUND: "[OK]",
                ANSWER_TYPE_NOT_FOUND: "[?]",
                ANSWER_TYPE_PARTIAL: "[!]",
                ANSWER_TYPE_AMBIGUOUS: "[~]"
            }
            lines.append(f"Status: {type_icons.get(self.answer_type, '[?]')} {self.answer_type.upper()}")
            lines.append(f"Confidence: {self.confidence.upper()}")
            lines.append("")
            
            # Main answer
            lines.append("ANSWER:")
            lines.append("-" * 40)
            lines.append(self.answer_text)
            lines.append("")
            
            # Reasoning
            if self.reasoning:
                lines.append("REASONING:")
                lines.append("-" * 40)
                lines.append(self.reasoning)
                lines.append("")
            
            # Citations
            if self.citations:
                lines.append("SOURCES:")
                lines.append("-" * 40)
                for i, citation in enumerate(self.citations, 1):
                    location = getattr(citation, 'page_number', None)
                    if location:
                        lines.append(f"[{i}] {citation.source_file} (Page {location})")
                    else:
                        lines.append(f"[{i}] {citation.source_file}")
            
            lines.append("=" * 60)
            
        elif style == 'simple':
            lines.append(self.answer_text)
            if self.citations:
                lines.append("")
                sources = [c.source_file for c in self.citations]
                lines.append(f"Sources: {', '.join(set(sources))}")
        
        elif style == 'short':
            lines.append(self.answer_text)
        
        return "\n".join(lines)


# ============================================================================
# ANSWER GENERATOR CLASS
# ============================================================================

class AnswerGenerator:
    """
    Generates answers from retrieved context with proper citations.
    
    This class handles:
    1. Analyzing retrieved context for relevance
    2. Generating coherent answers from context
    3. Detecting when information is not in documents
    4. Providing honest "not found" responses
    5. Adding proper citations
    
    The key philosophy is honesty - the system should clearly indicate
    when it cannot find information in the uploaded documents.
    
    Example:
        >>> generator = AnswerGenerator()
        >>> answer = generator.generate(
        ...     query="What is the capital of France?",
        ...     context=retrieved_context
        ... )
        >>> print(answer.format_for_display())
    """
    
    def __init__(
        self,
        include_reasoning: bool = True,
        min_confidence_threshold: float = LOW_CONFIDENCE,
        max_citations: int = 5,
        llm_provider: str = None
    ):
        """
        Initialize the AnswerGenerator.
        
        Args:
            include_reasoning: Include reasoning in answer
            min_confidence_threshold: Minimum score to consider relevant
            max_citations: Maximum citations to include
            llm_provider: LLM provider for advanced generation (optional)
        """
        self.include_reasoning = include_reasoning
        self.min_confidence_threshold = min_confidence_threshold
        self.max_citations = max_citations
        self.llm_provider = llm_provider
        
        logger.info(f"AnswerGenerator initialized")
        logger.info(f"  Include reasoning: {include_reasoning}")
        logger.info(f"  Min confidence: {min_confidence_threshold}")
    
    def generate(
        self,
        query: str,
        retrieved_results: List[Dict],
        total_documents: int = 0
    ) -> GeneratedAnswer:
        """
        Generate an answer from retrieved results.
        
        This is the main method that:
        1. Analyzes retrieved context
        2. Determines if answer can be provided
        3. Generates answer with citations
        4. Handles "not found" case
        
        Args:
            query: User's question
            retrieved_results: List of retrieved chunks with metadata
            total_documents: Total documents in index
            
        Returns:
            GeneratedAnswer object
        """
        logger.info(f"Generating answer for: '{query[:50]}...'")
        
        # Check if we have any results
        if not retrieved_results:
            return self._generate_not_found_answer(
                query,
                reason="No documents have been uploaded to search.",
                total_docs=total_documents
            )
        
        # Extract relevance scores
        scores = [r.get('similarity_score', 0.0) for r in retrieved_results]
        max_score = max(scores) if scores else 0.0
        
        # Check if we have relevant content
        if max_score < self.min_confidence_threshold:
            return self._generate_not_found_answer(
                query,
                reason=f"Could not find relevant information in uploaded documents. (Best match: {max_score:.2f})",
                total_docs=total_documents,
                results=retrieved_results
            )
        
        # We have relevant content - generate answer
        return self._generate_found_answer(
            query,
            retrieved_results,
            max_score
        )
    
    def _generate_not_found_answer(
        self,
        query: str,
        reason: str,
        total_docs: int,
        results: List[Dict] = None
    ) -> GeneratedAnswer:
        """
        Generate an answer when information is not found.
        
        This is crucial for honesty - we clearly state that
        the information is not in the uploaded documents.
        
        Args:
            query: User's question
            reason: Why answer wasn't found
            total_docs: Total documents indexed
            results: Any weakly related results (optional)
            
        Returns:
            GeneratedAnswer indicating not found
        """
        # Build honest response
        answer_parts = []
        
        # Start with clear statement
        answer_parts.append(
            "I could not find specific information about this in the uploaded documents."
        )
        
        # Add context about what's available
        if total_docs > 0:
            answer_parts.append(
                f"I have {total_docs} document(s) indexed for search, but none contain "
                f"relevant information matching your question."
            )
        else:
            answer_parts.append(
                "No documents have been uploaded yet. Please upload documents "
                "first, then ask questions about their content."
            )
        
        # Build reasoning
        reasoning = (
            f"Analysis: Searched through {total_docs} document(s). "
            f"Maximum relevance score was below threshold ({self.min_confidence_threshold}). "
            f"Cannot provide answer from document content."
        )
        
        # Handle weakly related results if any
        if results and len(results) > 0:
            # Mention what we found that's somewhat related
            weak_content = []
            for r in results[:2]:
                content = r.get('content', '')[:100]
                weak_content.append(content)
            
            if weak_content:
                reasoning += " Some weakly related content was found but not sufficient for answering."
        
        # Create answer
        answer_text = " ".join(answer_parts)
        
        return GeneratedAnswer(
            answer_type=ANSWER_TYPE_NOT_FOUND,
            answer_text=answer_text,
            reasoning=reasoning,
            citations=[],
            confidence="none",
            context_used=False
        )
    
    def _generate_found_answer(
        self,
        query: str,
        results: List[Dict],
        max_score: float
    ) -> GeneratedAnswer:
        """
        Generate an answer when information is found.
        
        Args:
            query: User's question
            results: Retrieved results
            max_score: Maximum relevance score
            
        Returns:
            GeneratedAnswer with citations
        """
        # Determine confidence level
        if max_score >= HIGH_CONFIDENCE:
            confidence = "high"
        elif max_score >= MEDIUM_CONFIDENCE:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Extract relevant content
        relevant_contents = []
        citations = []
        
        for i, result in enumerate(results[:self.max_citations]):
            content = result.get('content', '')
            metadata = result.get('metadata', {})
            
            if content:
                relevant_contents.append(content)
                
                # Create citation
                citation = CitationSource(
                    chunk_id=i,
                    document_id=metadata.get('document_id', 'unknown'),
                    source_file=metadata.get('filename', 'unknown'),
                    source_path=metadata.get('source', 'unknown'),
                    file_type=metadata.get('file_type', 'unknown'),
                    content=content,
                    chunk_index=metadata.get('chunk_index', i),
                    similarity_score=result.get('similarity_score', 0.0),
                    metadata=metadata
                )
                citations.append(citation)
        
        # Generate answer text (synthesize from context)
        answer_text = self._synthesize_answer(query, relevant_contents)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            query,
            relevant_contents,
            citations,
            max_score
        )
        
        return GeneratedAnswer(
            answer_type=ANSWER_TYPE_FOUND,
            answer_text=answer_text,
            reasoning=reasoning,
            citations=citations,
            confidence=confidence,
            context_used=True
        )
    
    def _synthesize_answer(
        self,
        query: str,
        contents: List[str]
    ) -> str:
        """
        Synthesize an answer from retrieved contents.
        
        In a production system, this would call an LLM.
        For now, we create a simple synthesis.
        
        Args:
            query: User's question
            contents: Retrieved contents
            
        Returns:
            Synthesized answer
        """
        if not contents:
            return "No relevant information found."
        
        # Combine relevant contents
        combined = "\n\n".join(contents[:3])  # Use top 3
        
        # In production, this would call an LLM:
        # response = llm.generate(
        #     prompt=f"Based on these sources, answer: {query}\n\nSources:\n{combined}"
        # )
        
        # For now, create a simple answer
        answer = f"Based on the uploaded documents:\n\n"
        
        # Add first piece of content as answer
        main_content = contents[0]
        if len(main_content) > 300:
            main_content = main_content[:300] + "..."
        
        answer += main_content
        
        # Add note about additional context
        if len(contents) > 1:
            answer += f"\n\n(Additional related information found in {len(contents)-1} other location(s))"
        
        return answer
    
    def _generate_reasoning(
        self,
        query: str,
        contents: List[str],
        citations: List[CitationSource],
        max_score: float
    ) -> str:
        """
        Generate reasoning explanation.
        
        Args:
            query: User's question
            contents: Retrieved contents
            citations: Citation sources
            max_score: Maximum relevance score
            
        Returns:
            Reasoning explanation
        """
        # Build reasoning
        reasoning_parts = []
        
        # How we searched
        reasoning_parts.append(
            f"Search: I searched through the indexed documents for information "
            f"matching your question."
        )
        
        # What we found
        reasoning_parts.append(
            f"Found: Retrieved {len(contents)} relevant passage(s) with a maximum "
            f"relevance score of {max_score:.3f}."
        )
        
        # Sources used
        if citations:
            sources = list(set([c.source_file for c in citations]))
            reasoning_parts.append(
                f"Sources: Information extracted from: {', '.join(sources)}"
            )
        
        # Confidence explanation
        if max_score >= HIGH_CONFIDENCE:
            reasoning_parts.append(
                "Confidence: High - Strong match found in documents."
            )
        elif max_score >= MEDIUM_CONFIDENCE:
            reasoning_parts.append(
                "Confidence: Medium - Reasonable match found, some uncertainty."
            )
        else:
            reasoning_parts.append(
                "Confidence: Low - Weak match, information may not be exact answer."
            )
        
        return " | ".join(reasoning_parts)
    
    def generate_with_fallback(
        self,
        query: str,
        retrieved_results: List[Dict],
        total_documents: int = 0,
        allow_web_fallback: bool = False
    ) -> GeneratedAnswer:
        """
        Generate answer with optional web fallback.
        
        If information is not in documents, this can provide a helpful
        response about where to find the information.
        
        Args:
            query: User's question
            retrieved_results: Retrieved results
            total_documents: Total documents indexed
            allow_web_fallback: Whether to suggest web resources
            
        Returns:
            GeneratedAnswer
        """
        # First try to find in documents
        answer = self.generate(query, retrieved_results, total_documents)
        
        # If not found and fallback allowed, add helpful message
        if answer.answer_type == ANSWER_TYPE_NOT_FOUND and allow_web_fallback:
            # Add fallback suggestion
            fallback_message = (
                "\n\nNote: While this specific information is not in your uploaded documents, "
                "you could search for this topic online or in other sources. "
                "This system only answers questions based on the documents you upload."
            )
            answer.answer_text += fallback_message
            
            # Update reasoning
            answer.reasoning += " | Web fallback: Suggested user search externally."
        
        return answer


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def generate_answer(
    query: str,
    retrieved_results: List[Dict],
    total_documents: int = 0,
    **kwargs
) -> GeneratedAnswer:
    """
    Convenience function to generate an answer.
    
    Args:
        query: User's question
        retrieved_results: Retrieved results
        total_documents: Total documents
        **kwargs: Additional arguments
        
    Returns:
        GeneratedAnswer
    """
    generator = AnswerGenerator(**kwargs)
    return generator.generate(query, retrieved_results, total_documents)


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution for testing.
    """
    print("=" * 60)
    print("Answer Generator - Test")
    print("=" * 60)
    
    # Create generator
    generator = AnswerGenerator()
    
    # Test 1: Answer found
    print("\n--- Test 1: Answer Found ---")
    test_results = [
        {
            'content': 'Machine learning is a subset of artificial intelligence.',
            'similarity_score': 0.85,
            'metadata': {'filename': 'ml.txt', 'document_id': 'doc1'}
        },
        {
            'content': 'ML enables systems to learn from data.',
            'similarity_score': 0.72,
            'metadata': {'filename': 'ml.txt', 'document_id': 'doc1'}
        }
    ]
    
    answer = generator.generate("What is machine learning?", test_results, total_documents=1)
    print(answer.format_for_display())
    
    # Test 2: Answer not found
    print("\n--- Test 2: Answer Not Found ---")
    no_results = []
    
    answer = generator.generate(
        "What is quantum computing?", 
        no_results, 
        total_documents=3
    )
    print(answer.format_for_display())
    
    # Test 3: With web fallback
    print("\n--- Test 3: Not Found with Web Fallback ---")
    answer = generator.generate_with_fallback(
        "What is quantum computing?",
        no_results,
        total_documents=3,
        allow_web_fallback=True
    )
    print(answer.format_for_display())
    
    print("\n" + "=" * 60)
    print("Answer generator ready.")
    print("=" * 60)
