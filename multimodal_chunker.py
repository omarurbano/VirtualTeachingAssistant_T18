"""
Smart chunking for multimodal PDF content.

Creates searchable chunks from extracted PDF elements while preserving
semantic boundaries for different content types (text, tables, images).

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2025-03-10
"""

from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# CHUNK DATA STRUCTURE
# ============================================================================

class MultimodalChunk:
    """
    Represents a single searchable chunk from a PDF element.

    Can be text, table, or image description.
    """

    def __init__(
        self,
        content: str,
        element_type: str,
        page_number: int,
        bbox: tuple,
        element_id: str,
        document_id: str,
        filename: str,
        chunk_index: int,
        metadata: Dict = None
    ):
        self.content = content
        self.element_type = element_type  # 'text', 'table', 'image'
        self.page_number = page_number
        self.bbox = bbox
        self.element_id = element_id
        self.document_id = document_id
        self.filename = filename
        self.chunk_index = chunk_index
        self.metadata = metadata or {}

    def to_langchain_document(self):
        """Convert to LangChain Document format."""
        try:
            from langchain.schema import Document
        except ImportError:
            from langchain_core.documents import Document

        # Build comprehensive metadata
        meta = {
            'document_id': self.document_id,
            'filename': self.filename,
            'file_type': '.pdf',
            'element_type': self.element_type,
            'page_number': self.page_number,
            'bbox': self.bbox,
            'element_id': self.element_id,
            'chunk_index': self.chunk_index,
            **self.metadata
        }

        return Document(
            page_content=self.content,
            metadata=meta
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'content': self.content,
            'element_type': self.element_type,
            'page_number': self.page_number,
            'bbox': self.bbox,
            'element_id': self.element_id,
            'document_id': self.document_id,
            'filename': self.filename,
            'chunk_index': self.chunk_index,
            'metadata': self.metadata
        }


# ============================================================================
# MAIN CHUNKER CLASS
# ============================================================================

class MultimodalChunker:
    """
    Creates searchable chunks from extracted PDF elements.

    Strategies:
    - Text: Split long text blocks using RecursiveCharacterTextSplitter
    - Tables: Keep as single chunks (Markdown format)
    - Images: Create single chunks with caption + OCR text
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize chunker.

        Args:
            chunk_size: Maximum characters per text chunk
            chunk_overlap: Overlap between consecutive text chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Text splitter for long text blocks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )

    def create_chunks(
        self,
        pages: Dict[int, Any],  # Dict[int, PDFPage]
        file_id: str,
        filename: str,
        image_analyses: Dict[str, Dict] = None
    ) -> List[MultimodalChunk]:
        """
        Convert extracted PDF pages into searchable chunks.

        Args:
            pages: Dict from PyMuPDFExtractor.extract()
            file_id: Unique document identifier
            filename: Original filename
            image_analyses: Dict mapping element_id -> {caption, ocr_text, ...}

        Returns:
            List of MultimodalChunk objects
        """
        if image_analyses is None:
            image_analyses = {}

        chunks = []
        chunk_index = 0

        # Process pages in order
        for page_num in sorted(pages.keys()):
            page = pages[page_num]

            # 1. Process text blocks
            for block in page.text_blocks:
                # Skip very short blocks (likely noise)
                if len(block.text) < 10:
                    continue

                # Create chunks from this text block
                text_chunks = self._chunk_text(block.text)

                for i, chunk_text in enumerate(text_chunks):
                    chunk = MultimodalChunk(
                        content=chunk_text,
                        element_type='text',
                        page_number=page_num,
                        bbox=block.bbox,
                        element_id=f"{block.block_id}_chunk{i}",
                        document_id=file_id,
                        filename=filename,
                        chunk_index=chunk_index,
                        metadata={
                            'text_chunk': i,
                            'total_chunks': len(text_chunks),
                            'block_type': block.block_type,
                            'char_count': len(chunk_text)
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1

            # 2. Process tables
            for table in page.tables:
                # Convert table to Markdown
                markdown = table.to_markdown()

                if not markdown.strip():
                    continue

                chunk = MultimodalChunk(
                    content=markdown,
                    element_type='table',
                    page_number=page_num,
                    bbox=table.bbox,
                    element_id=table.element_id,
                    document_id=file_id,
                    filename=filename,
                    chunk_index=chunk_index,
                    metadata={
                        'table_rows': table.row_count,
                        'table_columns': table.col_count,
                        'has_headers': len(table.headers) > 0,
                        'char_count': len(markdown)
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

            # 3. Process images
            for image in page.images:
                analysis = image_analyses.get(image.element_id, {})

                # Build content from caption and OCR
                content_parts = []

                caption = analysis.get('caption', '')
                ocr_text = analysis.get('ocr_text', '')

                if caption:
                    content_parts.append(f"Image description: {caption}")

                if ocr_text and ocr_text.strip():
                    content_parts.append(f"Text in image: {ocr_text}")

                if not content_parts:
                    content = "[Image with no detectable text or caption]"
                else:
                    content = "\n\n".join(content_parts)

                chunk = MultimodalChunk(
                    content=content,
                    element_type='image',
                    page_number=page_num,
                    bbox=image.bbox,
                    element_id=image.element_id,
                    document_id=file_id,
                    filename=filename,
                    chunk_index=chunk_index,
                    metadata={
                        'image_caption': caption,
                        'ocr_text': ocr_text,
                        'has_text': analysis.get('has_text', False),
                        'caption_success': analysis.get('caption_success', False),
                        'ocr_success': analysis.get('ocr_success', False),
                        'image_width': image.width,
                        'image_height': image.height,
                        'image_format': 'png',
                        'image_path': analysis.get('image_path', '')
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

        logger.info(f"Created {len(chunks)} chunks from PDF pages")
        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split long text into chunks using text splitter.

        Args:
            text: Input text

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        # Use LangChain text splitter
        chunks = self.text_splitter.split_text(text)

        # Filter out empty chunks
        chunks = [c.strip() for c in chunks if c.strip()]

        return chunks

    def get_chunk_statistics(self, chunks: List[MultimodalChunk]) -> Dict[str, Any]:
        """
        Generate statistics about created chunks.

        Args:
            chunks: List of MultimodalChunk objects

        Returns:
            Dict with counts and averages
        """
        stats = {
            'total_chunks': len(chunks),
            'by_type': {
                'text': 0,
                'table': 0,
                'image': 0
            },
            'text_chars_total': 0,
            'tables_with_headers': 0,
            'images_with_captions': 0,
            'images_with_ocr': 0
        }

        for chunk in chunks:
            element_type = chunk.element_type
            stats['by_type'][element_type] += 1

            if element_type == 'text':
                stats['text_chars_total'] += len(chunk.content)

            elif element_type == 'table':
                if chunk.metadata.get('has_headers', False):
                    stats['tables_with_headers'] += 1

            elif element_type == 'image':
                if chunk.metadata.get('caption_success', False):
                    stats['images_with_captions'] += 1
                if chunk.metadata.get('ocr_success', False):
                    stats['images_with_ocr'] += 1

        # Averages
        if stats['by_type']['text'] > 0:
            stats['avg_text_chunk_chars'] = stats['text_chars_total'] / stats['by_type']['text']

        return stats


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_chunks_from_pdf(
    pdf_path: str,
    file_id: str,
    filename: str,
    extractor=None,
    analyzer=None,
    chunker=None,
    output_image_dir: str = None
) -> List[MultimodalChunk]:
    """
    End-to-end chunk creation from PDF.

    Args:
        pdf_path: Path to PDF file
        file_id: Unique document ID
        filename: Original filename
        extractor: PyMuPDFExtractor instance (created if None)
        analyzer: ImageAnalyzer instance (created if None)
        chunker: MultimodalChunker instance (created if None)
        output_image_dir: Directory to save extracted images

    Returns:
        List of MultimodalChunk objects
    """
    # Import here to avoid circular imports
    from pdf_extractor import PyMuPDFExtractor
    from image_analyzer import create_image_analyzer

    # Create components if not provided
    if extractor is None:
        extractor = PyMuPDFExtractor(extract_images=True, extract_tables=True)

    if analyzer is None:
        try:
            analyzer = create_image_analyzer()
        except Exception as analyzer_error:
            logger.warning(f"Failed to create image analyzer: {analyzer_error}. Using simple analyzer.")
            from image_analyzer import SimpleImageAnalyzer
            analyzer = SimpleImageAnalyzer()

    if chunker is None:
        chunker = MultimodalChunker()

    # Step 1: Extract all elements from PDF
    pages = extractor.extract(pdf_path)

    # Step 2: Save images to disk if output dir provided
    image_analyses = {}
    if output_image_dir:
        import os
        os.makedirs(output_image_dir, exist_ok=True)

        # Collect all images for batch analysis
        all_images = []
        for page in pages.values():
            for image in page.images:
                all_images.append({
                    'element_id': image.element_id,
                    'image_bytes': image.image_bytes
                })

        # Batch analyze images
        if all_images:
            logger.info(f"Analyzing {len(all_images)} images...")
            try:
                image_analyses = analyze_images_batch(all_images, analyzer)
            except Exception as batch_error:
                logger.warning(f"Image batch analysis failed: {batch_error}. Continuing without image analysis.")
                image_analyses = {}

            # Save images to disk
            for page in pages.values():
                for image in page.images:
                    try:
                        filepath = extractor.save_image_to_file(image, output_image_dir)
                        if filepath:
                            # Store relative path for serving
                            image.saved_path = filepath
                            # Add to analyses
                            if image.element_id in image_analyses:
                                image_analyses[image.element_id]['image_path'] = filepath
                    except Exception as save_error:
                        logger.warning(f"Failed to save image: {save_error}")

    # Step 3: Create chunks
    chunks = chunker.create_chunks(pages, file_id, filename, image_analyses)

    logger.info(f"Created {len(chunks)} chunks from PDF: {filename}")
    return chunks


def analyze_images_batch(
    images: List[Dict],
    analyzer=None,
    batch_size: int = 4
) -> Dict[str, Dict]:
    """
    Analyze multiple images in batches.

    Args:
        images: List of {'element_id': str, 'image_bytes': bytes}
        analyzer: ImageAnalyzer instance
        batch_size: Process N images at a time

    Returns:
        Dict mapping element_id -> analysis result
    """
    if analyzer is None:
        from image_analyzer import create_image_analyzer
        analyzer = create_image_analyzer()

    results = {}

    for i in range(0, len(images), batch_size):
        batch = images[i:i+batch_size]

        for img_data in batch:
            element_id = img_data['element_id']
            image_bytes = img_data['image_bytes']

            try:
                analysis = analyzer.analyze(image_bytes)
                results[element_id] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze image {element_id}: {e}")
                results[element_id] = {
                    'caption': '',
                    'ocr_text': '',
                    'has_text': False,
                    'caption_success': False,
                    'ocr_success': False,
                    'error': str(e)
                }

    return results
