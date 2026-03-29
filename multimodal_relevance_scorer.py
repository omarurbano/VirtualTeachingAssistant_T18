"""
Multimodal Relevance Scoring System
====================================

This module provides relevance scoring for multimodal content (images, tables, audio)
using a hybrid approach that combines embedding-based semantic similarity with
keyword matching and content-type specific enhancements.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2026-03-28
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

# ============================================================================
# THIRD-PARTY LIBRARY IMPORTS
# ============================================================================

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy not installed - relevance scoring will be limited")

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ============================================================================
# MULTIMODAL RELEVANCE SCORER CLASS
# ============================================================================

class MultimodalRelevanceScorer:
    """
    Computes relevance scores between queries and multimodal content.
    
    Combines embedding-based similarity with keyword matching and
    content-type specific signals for robust relevance assessment.
    
    Supports scoring for:
    - Text chunks
    - Image chunks (with chart/graph metadata)
    - Table chunks (with column/structure metadata)
    - Audio chunks (with speaker/tone metadata)
    
    Attributes:
        embedding_manager: Instance of embedding manager for generating embeddings
        keyword_weight: Weight for keyword matching component (default: 0.3)
        semantic_weight: Weight for semantic similarity component (default: 0.7)
    """
    
    def __init__(self, embedding_manager):
        """
        Initialize the relevance scorer.
        
        Args:
            embedding_manager: Instance of embedding manager (EmbeddingManager or SimpleEmbeddingManager)
        """
        self.embedding_manager = embedding_manager
        self.keyword_weight = 0.3
        self.semantic_weight = 0.7
        
        logger.info("MultimodalRelevanceScorer initialized")
    
    def compute_relevance(
        self, 
        query: str, 
        content_chunks: List[Any]
    ) -> List[Tuple[Any, float, Dict]]:
        """
        Compute relevance scores for content chunks against a query.
        
        Uses a hybrid scoring approach combining:
        1. Semantic similarity (cosine similarity of embeddings)
        2. Keyword matching (Jaccard + term frequency)
        3. Content-type specific enhancements
        
        Args:
            query: User query string
            content_chunks: List of document-like objects (with page_content/content and metadata)
            
        Returns:
            List of tuples (chunk, relevance_score, score_breakdown) sorted by score descending
        """
        if not content_chunks:
            return []
        
        # Extract content text from chunks
        chunk_texts = []
        for chunk in content_chunks:
            if hasattr(chunk, 'page_content'):
                chunk_texts.append(chunk.page_content)
            elif hasattr(chunk, 'content'):
                chunk_texts.append(chunk.content)
            else:
                chunk_texts.append(str(chunk))
        
        # Compute semantic similarity scores
        semantic_scores = self._compute_semantic_similarity(query, chunk_texts)
        
        # Compute keyword matching scores
        keyword_scores = self._compute_keyword_matching(query, chunk_texts)
        
        # Compute content-type specific enhancements
        type_scores = self._compute_type_specific_enhancements(query, content_chunks)
        
        # Combine scores
        result = []
        
        for i, chunk in enumerate(content_chunks):
            semantic_score = semantic_scores[i] if i < len(semantic_scores) else 0.0
            keyword_score = keyword_scores[i] if i < len(keyword_scores) else 0.0
            type_score = type_scores[i] if i < len(type_scores) else 0.5
            
            # Weighted combination
            combined_score = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score +
                (1 - self.semantic_weight - self.keyword_weight) * type_score
            )
            
            # Ensure score is in [0, 1] range
            combined_score = max(0.0, min(1.0, combined_score))
            
            # Create breakdown for transparency
            breakdown = {
                'semantic': round(semantic_score, 4),
                'keyword': round(keyword_score, 4),
                'type_specific': round(type_score, 4),
                'combined': round(combined_score, 4),
                'weights': {
                    'semantic': self.semantic_weight,
                    'keyword': self.keyword_weight,
                    'type_specific': round(1 - self.semantic_weight - self.keyword_weight, 4)
                }
            }
            
            result.append((chunk, combined_score, breakdown))
        
        # Sort by combined score descending
        result.sort(key=lambda x: x[1], reverse=True)
        
        return result
    
    def _compute_semantic_similarity(
        self, 
        query: str, 
        chunk_texts: List[str]
    ) -> List[float]:
        """
        Compute semantic similarity between query and chunks using embeddings.
        
        Falls back to keyword-only scoring if embedding generation fails.
        
        Args:
            query: Query string
            chunk_texts: List of chunk text content
            
        Returns:
            List of similarity scores [0, 1]
        """
        if not chunk_texts:
            return []
        
        if not NUMPY_AVAILABLE:
            return [0.5] * len(chunk_texts)
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_manager.embed_query(query)
            
            # Generate chunk embeddings
            chunk_embeddings = self.embedding_manager.embed_documents(chunk_texts)
            
            # Compute cosine similarities
            return self._compute_cosine_similarity(query_embedding, chunk_embeddings)
            
        except Exception as e:
            logger.warning(f"Embedding generation failed, using neutral scores: {e}")
            return [0.5] * len(chunk_texts)
    
    def _compute_cosine_similarity(
        self, 
        query_embedding: List[float], 
        chunk_embeddings: List[List[float]]
    ) -> List[float]:
        """
        Compute cosine similarity between query and chunk embeddings.
        
        Args:
            query_embedding: Query embedding vector
            chunk_embeddings: List of chunk embedding vectors
            
        Returns:
            List of cosine similarity scores [0, 1]
        """
        if not chunk_embeddings:
            return []
        
        query = np.array(query_embedding)
        query_norm = np.linalg.norm(query)
        
        if query_norm == 0:
            return [0.0] * len(chunk_embeddings)
        
        normalized_query = query / query_norm
        
        similarities = []
        for chunk_emb in chunk_embeddings:
            chunk = np.array(chunk_emb)
            chunk_norm = np.linalg.norm(chunk)
            
            if chunk_norm == 0:
                similarities.append(0.0)
                continue
            
            normalized_chunk = chunk / chunk_norm
            similarity = float(np.dot(normalized_query, normalized_chunk))
            
            # Normalize to [0, 1] range (cosine similarity is [-1, 1])
            similarity = (similarity + 1) / 2
            
            similarities.append(similarity)
        
        return similarities
    
    def _compute_keyword_matching(
        self, 
        query: str, 
        chunk_texts: List[str]
    ) -> List[float]:
        """
        Compute keyword matching scores using Jaccard similarity and term frequency.
        
        Args:
            query: Query string
            chunk_texts: List of chunk text content
            
        Returns:
            List of keyword matching scores [0, 1]
        """
        query_terms = set(query.lower().split())
        if not query_terms:
            return [0.0] * len(chunk_texts)
        
        scores = []
        for chunk_text in chunk_texts:
            chunk_terms = set(chunk_text.lower().split())
            if not chunk_terms:
                scores.append(0.0)
                continue
            
            # Jaccard similarity
            intersection = len(query_terms.intersection(chunk_terms))
            union = len(query_terms.union(chunk_terms))
            jaccard = intersection / union if union > 0 else 0.0
            
            # Term frequency score (what fraction of query terms appear in chunk)
            term_matches = sum(1 for term in query_terms if term in chunk_terms)
            tf_score = term_matches / len(query_terms) if query_terms else 0.0
            
            # Combine Jaccard and term frequency
            score = 0.6 * jaccard + 0.4 * tf_score
            scores.append(score)
        
        return scores
    
    def _compute_type_specific_enhancements(
        self, 
        query: str,
        content_chunks: List[Any]
    ) -> List[float]:
        """
        Compute content-type specific relevance enhancements.
        
        Different modalities benefit from different scoring signals:
        - Images: Chart type recognition, OCR text matching
        - Tables: Column name matching, data value matching
        - Audio: Speaker matching, tone matching
        
        Args:
            query: Query string
            content_chunks: List of document-like objects
            
        Returns:
            List of type-specific enhancement scores [0, 1]
        """
        scores = []
        
        for chunk in content_chunks:
            # Get metadata
            metadata = {}
            if hasattr(chunk, 'metadata'):
                metadata = chunk.metadata or {}
            
            # Get chunk type
            chunk_type = metadata.get('chunk_type', metadata.get('element_type', 'text'))
            
            score = 0.5  # Base score
            
            if chunk_type == 'image':
                score = self._enhance_image_relevance(query, chunk, metadata)
            elif chunk_type == 'table':
                score = self._enhance_table_relevance(query, chunk, metadata)
            elif chunk_type == 'audio':
                score = self._enhance_audio_relevance(query, chunk, metadata)
            else:
                score = 0.5  # Text gets base score
            
            scores.append(score)
        
        return scores
    
    def _enhance_image_relevance(
        self, 
        query: str, 
        chunk: Any, 
        metadata: Dict
    ) -> float:
        """
        Enhance relevance scoring for image content.
        
        Checks for chart type matches, OCR text matches, and context matches.
        
        Args:
            query: Query string
            chunk: Image document chunk
            metadata: Chunk metadata
            
        Returns:
            Enhanced relevance score [0, 1]
        """
        score = 0.5
        query_lower = query.lower()
        
        # Check for chart type matches
        chart_type = metadata.get('chart_type', 'unknown')
        if chart_type != 'unknown':
            if chart_type in query_lower:
                score += 0.3
            elif any(term in query_lower for term in ['chart', 'graph', 'plot', 'diagram', 'visualization', 'figure']):
                score += 0.1
        
        # Check for OCR text matches
        text_blocks = metadata.get('text_blocks', [])
        if text_blocks:
            ocr_text = ' '.join([block.get('text', '') for block in text_blocks]).lower()
            query_terms = set(query_lower.split())
            ocr_terms = set(ocr_text.split())
            if query_terms and ocr_terms:
                overlap = len(query_terms.intersection(ocr_terms))
                if overlap > 0:
                    score += 0.2 * min(1.0, overlap / len(query_terms))
        
        # Check for context matches
        doc_type = metadata.get('document_type', '').lower()
        subject_area = metadata.get('subject_area', '').lower()
        
        if doc_type and doc_type in query_lower:
            score += 0.1
        if subject_area and subject_area in query_lower:
            score += 0.1
        
        return min(1.0, score)
    
    def _enhance_table_relevance(
        self, 
        query: str, 
        chunk: Any, 
        metadata: Dict
    ) -> float:
        """
        Enhance relevance scoring for table content.
        
        Checks for column name matches, data value matches, and structural matches.
        
        Args:
            query: Query string
            chunk: Table document chunk
            metadata: Chunk metadata
            
        Returns:
            Enhanced relevance score [0, 1]
        """
        score = 0.5
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        # Check for column name matches
        column_details = metadata.get('column_details', [])
        if column_details:
            column_headers = [col.get('header', '').lower() for col in column_details]
            column_text = ' '.join(column_headers)
            column_terms = set(column_text.split())
            
            if query_terms and column_terms:
                overlap = len(query_terms.intersection(column_terms))
                if overlap > 0:
                    score += 0.3 * min(1.0, overlap / len(query_terms))
        
        # Check for data value matches (for numeric queries)
        query_numbers = re.findall(r'\d+\.?\d*', query_lower)
        if query_numbers:
            data_points = metadata.get('data_points', [])
            if data_points:
                data_point_text = ' '.join([str(dp.get('value', '')) for dp in data_points]).lower()
                number_matches = sum(1 for num in query_numbers if num in data_point_text)
                if number_matches > 0:
                    score += 0.2 * min(1.0, number_matches / len(query_numbers))
        
        # Check for structural matches
        structure = metadata.get('table_structure', {})
        if structure.get('row_count', 0) > 0 and any(term in query_lower for term in 
                                                    ['row', 'record', 'entry', 'data', 'entries']):
            score += 0.1
        if structure.get('column_count', 0) > 0 and any(term in query_lower for term in 
                                                       ['column', 'field', 'attribute', 'fields']):
            score += 0.1
        
        return min(1.0, score)
    
    def _enhance_audio_relevance(
        self, 
        query: str, 
        chunk: Any, 
        metadata: Dict
    ) -> float:
        """
        Enhance relevance scoring for audio content.
        
        Checks for speaker matches, transcript text matches, and tone matches.
        
        Args:
            query: Query string
            chunk: Audio document chunk
            metadata: Chunk metadata
            
        Returns:
            Enhanced relevance score [0, 1]
        """
        score = 0.5
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        # Check for speaker matches
        speaker = metadata.get('speaker', '').lower()
        if speaker and speaker != 'unknown':
            if speaker in query_lower:
                score += 0.3
            elif any(term in query_lower for term in ['speaker', 'person', 'talker', 'who said']):
                score += 0.1
        
        # Check for transcript text matches
        chunk_text = ''
        if hasattr(chunk, 'page_content'):
            chunk_text = chunk.page_content
        elif hasattr(chunk, 'content'):
            chunk_text = chunk.content
        
        chunk_terms = set(chunk_text.lower().split())
        if query_terms and chunk_terms:
            overlap = len(query_terms.intersection(chunk_terms))
            if overlap > 0:
                score += 0.3 * min(1.0, overlap / len(query_terms))
        
        # Check for tone/emotion matches
        tone = metadata.get('tone', '').lower()
        if tone and tone != 'neutral':
            emotion_terms = ['happy', 'sad', 'angry', 'excited', 'frustrated', 'neutral', 'calm', 'professional']
            if any(emotion in query_lower for emotion in emotion_terms):
                if tone in query_lower:
                    score += 0.2
                elif any(emotion in query_lower for emotion in emotion_terms if emotion != tone):
                    score -= 0.1  # Penalty for mismatched emotion
        
        # Check for temporal matches
        timestamp_str = metadata.get('timestamp_str', '')
        if timestamp_str and any(term in query_lower for term in 
                                ['beginning', 'start', 'end', 'middle', 'first', 'last', 'early']):
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def rerank_results(
        self,
        query: str,
        initial_results: List[Any],
        top_k: int = None
    ) -> List[Tuple[Any, float, Dict]]:
        """
        Re-rank initial search results using multimodal relevance scoring.
        
        This method takes results from the vector store similarity search
        and re-ranks them using the hybrid scoring approach for better
        multimodal content understanding.
        
        Args:
            query: User query string
            initial_results: List of results from vector store (Document-like objects)
            top_k: Number of top results to return (None = all)
            
        Returns:
            Re-ranked list of (chunk, score, breakdown) tuples
        """
        if not initial_results:
            return []
        
        scored_results = self.compute_relevance(query, initial_results)
        
        if top_k is not None:
            scored_results = scored_results[:top_k]
        
        return scored_results


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_relevance_scorer(embedding_manager) -> MultimodalRelevanceScorer:
    """
    Factory function to create a MultimodalRelevanceScorer.
    
    Args:
        embedding_manager: Instance of embedding manager
        
    Returns:
        Configured MultimodalRelevanceScorer instance
    """
    return MultimodalRelevanceScorer(embedding_manager)


# ============================================================================
# MAIN TEST
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Multimodal Relevance Scorer - Test")
    print("=" * 60)
    
    # Create mock embedding manager
    class MockEmbeddingManager:
        def embed_query(self, text):
            return [hash(c) % 100 / 100.0 for c in text[:384]] + [0.0] * (384 - len(text))
        
        def embed_documents(self, texts):
            return [self.embed_query(t) for t in texts]
    
    mock_manager = MockEmbeddingManager()
    scorer = MultimodalRelevanceScorer(mock_manager)
    
    # Create test chunks
    class TestChunk:
        def __init__(self, content, metadata):
            self.page_content = content
            self.metadata = metadata
    
    chunks = [
        TestChunk("The bar chart shows revenue growth", {
            'chunk_type': 'image', 'chart_type': 'bar', 'subject_area': 'finance'
        }),
        TestChunk("Revenue | Profit | Year\n100 | 20 | 2023\n150 | 30 | 2024", {
            'chunk_type': 'table', 'column_details': [
                {'header': 'Revenue'}, {'header': 'Profit'}, {'header': 'Year'}
            ]
        }),
        TestChunk("Speaker 1 discussed the quarterly results", {
            'chunk_type': 'audio', 'speaker': 'Speaker 1', 'tone': 'professional'
        }),
        TestChunk("Machine learning is a subset of artificial intelligence", {
            'chunk_type': 'text'
        })
    ]
    
    query = "What is the revenue in the chart?"
    
    results = scorer.compute_relevance(query, chunks)
    
    print(f"\nQuery: '{query}'")
    print(f"\nResults (sorted by relevance):")
    for i, (chunk, score, breakdown) in enumerate(results):
        print(f"\n  {i+1}. Score: {score:.4f} | Type: {chunk.metadata.get('chunk_type', 'text')}")
        print(f"     Content: {chunk.page_content[:60]}...")
        print(f"     Breakdown: semantic={breakdown['semantic']:.3f}, keyword={breakdown['keyword']:.3f}, type={breakdown['type_specific']:.3f}")
    
    print("\n" + "=" * 60)
    print("MultimodalRelevanceScorer ready for use.")
    print("=" * 60)
