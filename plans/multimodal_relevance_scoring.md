# Multimodal Relevance Scoring System Specification

## Overview
This document specifies the implementation of a multimodal relevance scoring system that computes similarity between user queries and multimodal content (images, tables, audio segments) using Gemini Embedding 2.0 embeddings.

## Target Files
1. New utility class: `MultimodalRelevanceScorer` (to be created)
2. Modifications to `app.py` - RAG pipeline and answer generation
3. Potential enhancements to `embedding_manager.py` - if needed for scoring utilities

## Core Concepts

### 1. Embedding-Based Similarity
- Use cosine similarity between query embeddings and content embeddings
- Gemini Embedding 2.0 provides unified embedding space for all modalities
- Same embedding model used for queries and all content types ensures comparability

### 2. Hybrid Scoring Approach
Combine multiple signals for robust relevance scoring:
- Semantic similarity (cosine similarity of embeddings)
- Keyword matching (exact and fuzzy matches)
- Content-type specific signals (e.g., chart type matching for images)
- Recency and importance factors (if applicable)

### 3. Content-Type Specific Enhancements
Different modalities benefit from different scoring enhancements:
- Images: Chart type recognition, OCR text matching, object detection
- Tables: Column name matching, data value matching, structural similarity
- Audio: Speaker matching, keyword matching in transcript, tone matching

## Implementation Details

### 1. MultimodalRelevanceScorer Class
Create a new utility class to handle relevance scoring:

```python
class MultimodalRelevanceScorer:
    """
    Computes relevance scores between queries and multimodal content.
    
    Combines embedding-based similarity with keyword matching and
    content-type specific signals for robust relevance assessment.
    """
    
    def __init__(self, embedding_manager):
        """
        Initialize the relevance scorer.
        
        Args:
            embedding_manager: Instance of embedding manager for generating embeddings
        """
        self.embedding_manager = embedding_manager
        self.keyword_weight = 0.3  # Weight for keyword matching component
        self.semantic_weight = 0.7  # Weight for semantic similarity component
        
    def compute_relevance(self, query: str, content_chunks: List[DocumentChunk]) -> List[Tuple[DocumentChunk, float, Dict]]:
        """
        Compute relevance scores for content chunks against a query.
        
        Args:
            query: User query string
            content_chunks: List of DocumentChunk objects to score
            
        Returns:
            List of tuples (chunk, relevance_score, score_breakdown) sorted by score descending
        """
        if not content_chunks:
            return []
            
        # Generate query embedding
        query_embedding = self.embedding_manager.embed_query(query)
        
        # Extract text content for embedding generation
        chunk_texts = [chunk.content for chunk in content_chunks]
        
        # Generate embeddings for all chunks
        try:
            chunk_embeddings = self.embedding_manager.embed_documents(chunk_texts)
        except Exception as e:
            logger.error(f"Failed to generate embeddings for relevance scoring: {e}")
            # Fallback to keyword-only scoring
            return self._keyword_only_scoring(query, content_chunks)
        
        # Compute semantic similarity scores
        semantic_scores = self._compute_cosine_similarity(query_embedding, chunk_embeddings)
        
        # Compute keyword matching scores
        keyword_scores = self._compute_keyword_matching(query, content_chunks)
        
        # Compute content-type specific enhancements
        type_scores = self._compute_type_specific_enhancements(query, content_chunks)
        
        # Combine scores
        combined_scores = []
        score_breakdowns = []
        
        for i, (semantic_score, keyword_score, type_score) in enumerate(
                zip(semantic_scores, keyword_scores, type_scores)):
            
            # Weighted combination
            combined_score = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score +
                (1 - self.semantic_weight - self.keyword_weight) * type_score
            )
            
            # Ensure score is in [0, 1] range
            combined_score = max(0.0, min(1.0, combined_score))
            
            combined_scores.append((content_chunks[i], combined_score))
            
            # Store breakdown for debugging/explanation
            score_breakdowns.append({
                'semantic': semantic_score,
                'keyword': keyword_score,
                'type_specific': type_score,
                'combined': combined_score,
                'weights': {
                    'semantic': self.semantic_weight,
                    'keyword': self.keyword_weight,
                    'type_specific': 1 - self.semantic_weight - self.keyword_weight
                }
            })
        
        # Sort by combined score descending
        scored_chunks = list(zip(combined_scores, score_breakdowns))
        scored_chunks.sort(key=lambda x: x[0][1], reverse=True)
        
        # Unpack for return format
        result = [(chunk, score, breakdown) for (chunk, score), breakdown in scored_chunks]
        
        return result
    
    def _compute_cosine_similarity(self, query_embedding: List[float], 
                                 chunk_embeddings: List[List[float]]) -> List[float]:
        """Compute cosine similarity between query and chunk embeddings."""
        import numpy as np
        
        if not chunk_embeddings:
            return []
            
        # Normalize embeddings
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return [0.0] * len(chunk_embeddings)
            
        normalized_query = query_embedding / query_norm
        
        similarities = []
        for chunk_emb in chunk_embeddings:
            chunk_norm = np.linalg.norm(chunk_emb)
            if chunk_norm == 0:
                similarities.append(0.0)
                continue
                
            normalized_chunk = chunk_emb / chunk_norm
            similarity = np.dot(normalized_query, normalized_chunk)
            similarities.append(float(similarity))
            
        return similarities
    
    def _compute_keyword_matching(self, query: str, 
                                content_chunks: List[DocumentChunk]) -> List[float]:
        """Compute keyword matching scores."""
        query_terms = set(query.lower().split())
        if not query_terms:
            return [0.0] * len(content_chunks)
        
        scores = []
        for chunk in content_chunks:
            chunk_terms = set(chunk.content.lower().split())
            if not chunk_terms:
                scores.append(0.0)
                continue
                
            # Jaccard similarity
            intersection = len(query_terms.intersection(chunk_terms))
            union = len(query_terms.union(chunk_terms))
            jaccard = intersection / union if union > 0 else 0.0
            
            # Also consider term frequency
            term_matches = sum(1 for term in query_terms if term in chunk_terms)
            tf_score = term_matches / len(query_terms) if query_terms else 0.0
            
            # Combine Jaccard and term frequency
            score = 0.6 * jaccard + 0.4 * tf_score
            scores.append(score)
            
        return scores
    
    def _compute_type_specific_enhancements(self, query: str,
                                          content_chunks: List[DocumentChunk]) -> List[float]:
        """Compute content-type specific relevance enhancements."""
        scores = []
        
        for chunk in content_chunks:
            score = 0.5  # Base score
            
            # Image-specific enhancements
            if chunk.chunk_type == 'image':
                score = self._enhance_image_relevance(query, chunk)
                
            # Table-specific enhancements
            elif chunk.chunk_type == 'table':
                score = self._enhance_table_relevance(query, chunk)
                
            # Audio-specific enhancements
            elif chunk.chunk_type == 'audio':
                score = self._enhance_audio_relevance(query, chunk)
                
            # Text gets base score (no specific enhancements yet)
            else:
                score = 0.5
                
            scores.append(score)
            
        return scores
    
    def _enhance_image_relevance(self, query: str, chunk: DocumentChunk) -> float:
        """Enhance relevance scoring for image content."""
        score = 0.5  # Base
        
        # Check for chart type matches in query
        query_lower = query.lower()
        chart_type = chunk.metadata.get('chart_type', 'unknown')
        
        if chart_type != 'unknown':
            if chart_type in query_lower:
                score += 0.3  # Strong match
            elif any(chart_term in query_lower for chart_term in 
                    ['chart', 'graph', 'plot', 'diagram', 'visualization']):
                score += 0.1  # Weak match for general chart terms
        
        # Check for OCR text matches
        text_blocks = chunk.metadata.get('text_blocks', [])
        if text_blocks:
            ocr_text = ' '.join([block.get('text', '') for block in text_blocks]).lower()
            query_terms = set(query_lower.split())
            ocr_terms = set(ocr_text.split())
            if query_terms and ocr_terms:
                overlap = len(query_terms.intersection(ocr_terms))
                if overlap > 0:
                    score += 0.2 * min(1.0, overlap / len(query_terms))
        
        # Check for context matches
        context = chunk.metadata.get('context', {})
        doc_type = context.get('document_type', '').lower()
        subject_area = context.get('subject_area', '').lower()
        
        if doc_type and doc_type in query_lower:
            score += 0.1
        if subject_area and subject_area in query_lower:
            score += 0.1
            
        return min(1.0, score)
    
    def _enhance_table_relevance(self, query: str, chunk: DocumentChunk) -> float:
        """Enhance relevance scoring for table content."""
        score = 0.5  # Base
        
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        # Check for column name matches
        column_details = chunk.metadata.get('column_details', [])
        if column_details:
            column_headers = [col.get('header', '').lower() for col in column_details]
            column_text = ' '.join(column_headers)
            column_terms = set(column_text.split())
            
            if query_terms and column_terms:
                overlap = len(query_terms.intersection(column_terms))
                if overlap > 0:
                    score += 0.3 * min(1.0, overlap / len(query_terms))
        
        # Check for data value matches (for numeric queries)
        # Look for numbers in query and see if they appear in table data
        import re
        query_numbers = re.findall(r'\d+\.?\d*', query_lower)
        if query_numbers:
            # Check if these numbers appear in column details or data points
            data_points = chunk.metadata.get('data_points', [])
            if data_points:
                data_point_text = ' '.join([str(dp.get('value', '')) for dp in data_points]).lower()
                number_matches = sum(1 for num in query_numbers if num in data_point_text)
                if number_matches > 0:
                    score += 0.2 * min(1.0, number_matches / len(query_numbers))
        
        # Check for structural matches
        structure = chunk.metadata.get('table_structure', {})
        if structure.get('row_count', 0) > 0 and any(term in query_lower for term in 
                                                    ['row', 'record', 'entry', 'data']):
            score += 0.1
        if structure.get('column_count', 0) > 0 and any(term in query_lower for term in 
                                                       ['column', 'field', 'attribute']):
            score += 0.1
            
        return min(1.0, score)
    
    def _enhance_audio_relevance(self, query: str, chunk: DocumentChunk) -> float:
        """Enhance relevance scoring for audio content."""
        score = 0.5  # Base
        
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        # Check for speaker matches
        speaker = chunk.metadata.get('speaker', '').lower()
        if speaker and speaker != 'unknown':
            if speaker in query_lower:
                score += 0.3
            elif any(term in query_lower for term in ['speaker', 'person', 'talker']):
                score += 0.1
        
        # Check for transcript text matches
        # The chunk content already contains the transcript text
        chunk_terms = set(chunk.content.lower().split())
        if query_terms and chunk_terms:
            overlap = len(query_terms.intersection(chunk_terms))
            if overlap > 0:
                score += 0.3 * min(1.0, overlap / len(query_terms))
        
        # Check for tone/emotion matches
        tone = chunk.metadata.get('tone', '').lower()
        if tone and tone != 'neutral':
            emotion_terms = ['happy', 'sad', 'angry', 'excited', 'frustrated', 'neutral', 'calm']
            if any(emotion in query_lower for emotion in emotion_terms):
                if tone in query_lower:
                    score += 0.2
                elif any(emotion in query_lower for emotion in emotion_terms if emotion != tone):
                    score -= 0.1  # Penalty for mismatched emotion
        
        # Check for temporal matches
        timestamp_str = chunk.metadata.get('timestamp_str', '')
        if timestamp_str and any(term in query_lower for term in 
                                ['beginning', 'start', 'end', 'middle', 'first', 'last']):
            # Simple heuristic - could be enhanced
            score += 0.1
            
        return min(1.0, score)
    
    def _keyword_only_scoring(self, query: str, 
                            content_chunks: List[DocumentChunk]) -> List[Tuple[DocumentChunk, float, Dict]]:
        """Fallback to keyword-only scoring when embeddings fail."""
        keyword_scores = self._compute_keyword_matching(query, content_chunks)
        scored_chunks = [(chunk, score) for chunk, score in zip(content_chunks, keyword_scores)]
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Create minimal breakdown
        breakdowns = [{
            'semantic': 0.0,
            'keyword': score,
            'type_specific': 0.5,
            'combined': score,
            'note': 'Keyword-only scoring due to embedding failure'
        } for _, score in scored_chunks]
        
        return [(chunk, score, breakdown) for (chunk, score), breakdown in zip(scored_chunks, breakdowns)]
```

### 2. Integration with RAG Pipeline
Modify the RAG pipeline in `app.py` to use the relevance scorer:

In the `process_with_unified_processor` function or wherever results are prepared for the vector store, we don't need to change the storage, but we need to change how we retrieve and present results.

Actually, the vector store already does similarity search using embeddings. We can enhance that by:

1. Keeping the vector store for efficient approximate nearest neighbor search
2. Applying the multimodal relevance scorer as a re-ranking step on the top-K results

Or we could replace the vector store similarity search entirely with our scorer, but that would lose the efficiency benefits of ANN search.

Better approach: Use vector store for initial retrieval (get top 50 candidates), then re-rank with our multimodal scorer.

Modify the query processing in app.py:

```python
# After getting initial results from vector store
initial_results = app_state.vector_store.similarity_search(query_embedding, k=50)

# Then re-rank using multimodal relevance scorer
if hasattr(app_state, 'relevance_scorer'):
    reranked_results = app_state.relevance_scorer.compute_relevance(
        query, 
        [result for result in initial_results]  # Convert to DocumentChunk format if needed
    )
    # Take top K after re-ranking
    final_results = reranked_results[:app_config['MAX_CITATIONS']]
else:
    # Fallback to original behavior
    final_results = initial_results[:app_config['MAX_CITATIONS']]
```

### 3. Answer Generation Enhancements
Modify the answer generator to include relevance scores in the reasoning and potentially filter by minimum relevance threshold.

## Expected Benefits

1. **Improved Relevance**: Better matching of user intent to content through multiple signals
2. **Transparency**: Ability to explain why certain content was ranked highly
3. **Flexibility**: Easy to adjust weights and add new scoring signals
4. **Modality Awareness**: Scores that understand the unique characteristics of images, tables, and audio
5. **Fallback Safety**: Graceful degradation to keyword-only scoring if embeddings fail

## Implementation Order

1. Create the `MultimodalRelevanceScorer` class in a new utility file or in `embedding_manager.py`
2. Initialize it in the RAG application state
3. Modify the query processing pipeline to use re-ranking
4. Enhance the answer generator to display relevance scores
5. Add tests for the scoring system

## Dependencies
- numpy (for cosine similarity calculations) - already used in the codebase
- No additional major dependencies required

## Performance Considerations
- The scorer adds computational overhead but only runs on the top-K results from vector store
- Typical K values (10-50) keep performance impact minimal
- Embedding computations are cached where possible