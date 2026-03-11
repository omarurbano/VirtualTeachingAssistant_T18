# Advanced Multimodal PDF Processing Specification

## Overview

Implement a robust PDF processing pipeline that extracts **text, tables, and images** from PDFs, creates separate searchable chunks for each content type with rich metadata, and uses **multimodal embeddings** to enable semantic search across both text and visual content.

---

## 1. Architecture

### Processing Pipeline

```
PDF Upload
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 1. EXTRACT with PyMuPDF (fitz)                      │
│    - Text blocks with bounding boxes                │
│    - Images (extract as bytes)                      │
│    - Tables (via layout analysis)                   │
│    - Page-level metadata                            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 2. ANALYZE VISUAL ELEMENTS                          │
│    - For each image:                                │
│      • BLIP-2/CLIP: Generate caption                │
│      • OCR (pytesseract): Extract embedded text     │
│    - For tables:                                    │
│      • Convert to Markdown/JSON                     │
│      • Extract table structure                      │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 3. CREATE CHUNKS                                    │
│    - Text chunks (semantic boundaries)              │
│    - Image caption chunks (with OCR text)           │
│    - Table chunks (structured as text)              │
│    Each chunk has:                                  │
│      • content (text/caption/table)                 │
│      • metadata: {source, page, element_type,      │
│                   bbox, element_id, caption}        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 4. EMBEDDING                                       │
│    - Text chunks: sentence-transformers             │
│    - Image captions: sentence-transformers          │
│      (same embedding space for cross-modal search)  │
│    - Tables: sentence-transformers                  │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 5. INDEX in Vector Store                            │
│    - All chunks in same vector space                │
│    - Metadata filters for element_type              │
└─────────────────────────────────────────────────────┘
```

---

## 2. Detailed Implementation

### 2.1 PDF Extraction with PyMuPDF

**Installation:**
```bash
pip install pymupdf
```

**Module: `pdf_extractor.py`**

```python
"""
PDF Multimodal Extractor using PyMuPDF (fitz)
Extracts text, images, and tables with precise bounding boxes.
"""

import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
import os
from datetime import datetime

class PDFPage:
    """Represents a single PDF page with all its elements."""

    def __init__(self, page_number: int, page_obj):
        self.page_number = page_number
        self.page_obj = page_obj
        self.width = page_obj.rect.width
        self.height = page_obj.rect.height
        self.text_blocks = []
        self.images = []
        self.tables = []

class TextBlock:
    """A contiguous text region with bounding box."""

    def __init__(self, text: str, bbox: Tuple[float, float, float, float],
                 block_type: str = 'text'):
        self.text = text.strip()
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.block_type = block_type  # 'text', 'header', 'footer', 'caption'

class PDFImage:
    """An extracted image with metadata."""

    def __init__(self, image_bytes: bytes, bbox: Tuple[float, float, float, float],
                 page_number: int, image_index: int):
        self.image_bytes = image_bytes
        self.bbox = bbox
        self.page_number = page_number
        self.image_index = image_index
        self.element_id = f"img_p{page_number}_{image_index}"
        self.caption = None  # To be filled by BLIP-2
        self.ocr_text = None  # To be filled by OCR

class PDFTable:
    """A table extracted from PDF."""

    def __init__(self, table_data: List[List], bbox: Tuple[float, float, float, float],
                 page_number: int, table_index: int):
        self.table_data = table_data  # 2D list of cells
        self.bbox = bbox
        self.page_number = page_number
        self.table_index = table_index
        self.element_id = f"tbl_p{page_number}_{table_index}"
        self.markdown = None  # To be converted

class PyMuPDFExtractor:
    """
    Extracts all multimodal elements from a PDF using PyMuPDF.
    """

    def __init__(self, extract_images: bool = True, extract_tables: bool = True):
        self.extract_images = extract_images
        self.extract_tables = extract_tables

    def extract(self, pdf_path: str) -> Dict[int, PDFPage]:
        """
        Main extraction method.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict mapping page_number -> PDFPage object with all elements
        """
        doc = fitz.open(pdf_path)
        pages = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            pdf_page = PDFPage(page_num + 1, page)  # 1-indexed

            # 1. Extract text blocks
            text_blocks = self._extract_text_blocks(page)
            pdf_page.text_blocks = text_blocks

            # 2. Extract images
            if self.extract_images:
                images = self._extract_images(page, page_num + 1)
                pdf_page.images = images

            # 3. Extract tables
            if self.extract_tables:
                tables = self._extract_tables(page, page_num + 1)
                pdf_page.tables = tables

            pages[page_num + 1] = pdf_page

        doc.close()
        return pages

    def _extract_text_blocks(self, page) -> List[TextBlock]:
        """Extract text with bounding boxes."""
        blocks = []
        text_dict = page.get_text("dict")  # Returns structured dict

        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                # Concatenate lines
                lines = []
                for line in block["lines"]:
                    for span in line["spans"]:
                        lines.append(span["text"])
                text = " ".join(lines).strip()

                if text:
                    bbox = block["bbox"]  # (x0, y0, x1, y1)
                    blocks.append(TextBlock(text, bbox))

        return blocks

    def _extract_images(self, page, page_number: int) -> List[PDFImage]:
        """Extract images as PNG bytes."""
        images = []
        image_list = page.get_images(full=True)  # List of (xref, ...)

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                # Extract image as pixmap
                pix = fitz.Pixmap(page.parent, xref)
                if pix.n > 4:  # CMYK, convert to RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                image_bytes = pix.tobytes("png")
                bbox = self._find_image_bbox(page, xref)

                img_obj = PDFImage(image_bytes, bbox, page_number, img_index)
                images.append(img_obj)

                pix = None  # Free memory
            except Exception as e:
                print(f"Failed to extract image {xref} on page {page_number}: {e}")

        return images

    def _find_image_bbox(self, page, xref: int) -> Tuple[float, float, float, float]:
        """Find bounding box of image on page."""
        # Get all drawings and find matching xref
        for drawing in page.get_drawings():
            if drawing.get('xref') == xref:
                return drawing['rect']  # (x0, y0, x1, y1)

        # Fallback: return page bounds
        return (0, 0, page.rect.width, page.rect.height)

    def _extract_tables(self, page, page_number: int) -> List[PDFTable]:
        """
        Extract tables using heuristic approach.
        Note: For complex tables, consider using camelot-py or tabula-py.
        """
        tables = []

        # Simple heuristic: find text blocks arranged in grid
        # This is a basic implementation; for production use camelot
        text_blocks = self._extract_text_blocks(page)

        # Group by lines (y-coordinate)
        lines = {}
        for block in text_blocks:
            y_mid = (block.bbox[1] + block.bbox[3]) / 2
            line_key = round(y_mid / 5) * 5  # Snap to 5pt grid
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(block)

        # Check if any line has multiple blocks (potential table row)
        table_candidates = []
        for y, blocks in lines.items():
            if len(blocks) >= 2:  # At least 2 columns
                # Sort by x position
                blocks.sort(key=lambda b: b.bbox[0])
                table_candidates.append(blocks)

        # If we have multiple rows with similar column count, it's a table
        if len(table_candidates) >= 2:
            # Simple table reconstruction
            table_data = []
            for row in table_candidates:
                table_data.append([b.text for b in row])

            if table_data:
                # Calculate bounding box covering all rows
                all_bboxes = [b.bbox for row in table_candidates for b in row]
                x0 = min(b[0] for b in all_bboxes)
                y0 = min(b[1] for b in all_bboxes)
                x1 = max(b[2] for b in all_bboxes)
                y1 = max(b[3] for b in all_bboxes)

                table = PDFTable(table_data, (x0, y0, x1, y1), page_number, 0)
                table.markdown = self._convert_to_markdown(table_data)
                tables.append(table)

        return tables

    def _convert_to_markdown(self, table_data: List[List[str]]) -> str:
        """Convert 2D list to Markdown table."""
        if not table_data:
            return ""

        lines = []
        # Header row
        if table_data:
            lines.append("| " + " | ".join(table_data[0]) + " |")
            # Separator
            lines.append("| " + " | ".join(["---"] * len(table_data[0])) + " |")
            # Data rows
            for row in table_data[1:]:
                lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)
```

---

### 2.2 Multimodal Image Analysis

**Option A: BLIP-2 (Recommended - Local)**
```bash
pip install transformers torch pillow
```

**Module: `image_analyzer.py`**

```python
"""
Image Analysis using BLIP-2 for captioning and OCR.
"""

from transformers import Blip2Processor, Blip2ForConditionalGeneration
from PIL import Image
import pytesseract
import io
import torch

class ImageAnalyzer:
    """
    Analyzes images using BLIP-2 for captioning and pytesseract for OCR.
    """

    def __init__(self, device: str = None):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.blip_processor = None
        self.blip_model = None
        self._load_blip2()

    def _load_blip2(self):
        """Load BLIP-2 model."""
        print(f"Loading BLIP-2 on {self.device}...")
        model_name = "Salesforce/blip2-opt-2.7b"

        try:
            self.blip_processor = Blip2Processor.from_pretrained(model_name)
            self.blip_model = Blip2ForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if self.device == 'cuda' else torch.float32
            ).to(self.device)
            print("BLIP-2 loaded successfully")
        except Exception as e:
            print(f"Failed to load BLIP-2: {e}")
            self.blip_model = None

    def generate_caption(self, image_bytes: bytes) -> str:
        """
        Generate a descriptive caption for an image.

        Args:
            image_bytes: PNG/JPEG image data

        Returns:
            Caption string
        """
        if not self.blip_model:
            return "Image captioning model not available"

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            inputs = self.blip_processor(image, return_tensors="pt").to(self.device)
            generated_ids = self.blip_model.generate(**inputs, max_new_tokens=100)
            caption = self.blip_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]

            return caption.strip()
        except Exception as e:
            return f"Caption generation failed: {e}"

    def extract_ocr(self, image_bytes: bytes) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_bytes: PNG/JPEG image data

        Returns:
            OCR text string
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            ocr_text = pytesseract.image_to_string(image)
            return ocr_text.strip()
        except Exception as e:
            return f"OCR failed: {e}"

    def analyze(self, image_bytes: bytes) -> Dict[str, str]:
        """
        Comprehensive image analysis.

        Returns:
            {
                'caption': str,
                'ocr_text': str,
                'has_text': bool
            }
        """
        caption = self.generate_caption(image_bytes)
        ocr_text = self.extract_ocr(image_bytes)

        return {
            'caption': caption,
            'ocr_text': ocr_text,
            'has_text': len(ocr_text.strip()) > 0
        }
```

**Option B: CLIP for Zero-Shot Classification (Alternative)**
- Use CLIP to classify image content against predefined categories
- Faster but less descriptive than BLIP-2
- Good for determining image type (chart, diagram, photo, etc.)

---

### 2.3 Chunking Strategy

**Module: `multimodal_chunker.py`**

```python
"""
Smart chunking that preserves semantic boundaries for different content types.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict, Any

class MultimodalChunker:
    """
    Creates chunks from PDF elements with type-specific strategies.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Text splitter for long text blocks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )

    def create_chunks(self, pages: Dict[int, PDFPage], file_id: str, filename: str,
                      image_analyses: Dict[str, Dict] = None) -> List[Dict]:
        """
        Convert extracted PDF elements into searchable chunks.

        Args:
            pages: Dict from PyMuPDFExtractor.extract()
            file_id: Unique document ID
            filename: Original filename
            image_analyses: Dict mapping element_id -> {caption, ocr_text}

        Returns:
            List of chunk dicts with content and metadata
        """
        chunks = []
        chunk_index = 0

        for page_num, page in sorted(pages.items()):
            # 1. Process text blocks
            for block in page.text_blocks:
                # Skip very short blocks (likely noise)
                if len(block.text) < 10:
                    continue

                # Check if text is too long and needs splitting
                if len(block.text) > self.chunk_size:
                    # Split long text
                    text_chunks = self.text_splitter.split_text(block.text)
                    for i, chunk_text in enumerate(text_chunks):
                        chunk = self._make_chunk(
                            content=chunk_text,
                            element_type='text',
                            page=page_num,
                            bbox=block.bbox,
                            chunk_index=chunk_index,
                            file_id=file_id,
                            filename=filename,
                            element_id=f"txt_p{page_num}_{chunk_index}",
                            metadata={'text_chunk': i, 'total_chunks': len(text_chunks)}
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                else:
                    # Single chunk
                    chunk = self._make_chunk(
                        content=block.text,
                        element_type='text',
                        page=page_num,
                        bbox=block.bbox,
                        chunk_index=chunk_index,
                        file_id=file_id,
                        filename=filename,
                        element_id=f"txt_p{page_num}_{chunk_index}"
                    )
                    chunks.append(chunk)
                    chunk_index += 1

            # 2. Process tables
            for table in page.tables:
                # Convert table to searchable text format
                content = table.markdown if table.markdown else str(table.table_data)

                chunk = self._make_chunk(
                    content=content,
                    element_type='table',
                    page=page_num,
                    bbox=table.bbox,
                    chunk_index=chunk_index,
                    file_id=file_id,
                    filename=filename,
                    element_id=table.element_id,
                    metadata={
                        'table_structure': 'markdown',
                        'rows': len(table.table_data),
                        'columns': len(table.table_data[0]) if table.table_data else 0
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

            # 3. Process images
            for img in page.images:
                element_id = img.element_id
                analysis = image_analyses.get(element_id, {})

                # Combine caption and OCR text
                content_parts = []
                if analysis.get('caption'):
                    content_parts.append(f"Image description: {analysis['caption']}")
                if analysis.get('ocr_text'):
                    content_parts.append(f"Text in image: {analysis['ocr_text']}")

                content = "\n\n".join(content_parts) if content_parts else "[Image with no detectable text]"

                chunk = self._make_chunk(
                    content=content,
                    element_type='image',
                    page=page_num,
                    bbox=img.bbox,
                    chunk_index=chunk_index,
                    file_id=file_id,
                    filename=filename,
                    element_id=element_id,
                    metadata={
                        'image_caption': analysis.get('caption', ''),
                        'ocr_text': analysis.get('ocr_text', ''),
                        'has_text': analysis.get('has_text', False),
                        'image_format': 'png'
                    }
                )
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def _make_chunk(self, content: str, element_type: str, page: int,
                    bbox: tuple, chunk_index: int, file_id: str, filename: str,
                    element_id: str, metadata: Dict = None) -> Dict:
        """Create a standardized chunk dict."""
        chunk_meta = {
            'document_id': file_id,
            'filename': filename,
            'file_type': '.pdf',
            'element_type': element_type,
            'page_number': page,
            'bbox': bbox,  # (x0, y0, x1, y1)
            'element_id': element_id,
            'chunk_index': chunk_index,
            **(metadata or {})
        }

        return {
            'page_content': content,
            'metadata': chunk_meta
        }
```

---

### 2.4 Multimodal Embedding Strategy

**Key Insight:** Use **same embedding model** (sentence-transformers) for:
- Text chunks
- Image captions
- OCR text
- Table content (Markdown)

This ensures all modalities are in **shared vector space** for unified search.

**Implementation in `embedding_manager.py`:**

```python
# No changes needed! sentence-transformers handles all text equally well.
# Just ensure we pass:
#   - Raw text for text chunks
#   - "Image of: {caption}" for image chunks
#   - OCR text for image OCR
#   - Markdown table for tables

# Example:
texts_to_embed = []
for chunk in chunks:
    # For image chunks, prefix with type indicator
    if chunk['metadata']['element_type'] == 'image':
        prefix = "Image: "
    elif chunk['metadata']['element_type'] == 'table':
        prefix = "Table: "
    else:
        prefix = ""

    texts_to_embed.append(prefix + chunk['page_content'])

embeddings = embedding_manager.embed_documents(texts_to_embed)
```

**Why this works:** sentence-transformers are trained on diverse text; "Image: A bar chart showing..." and "A bar chart showing..." will have similar embeddings. The prefix helps distinguish modalities during retrieval.

---

### 2.5 Enhanced Retrieval with Normalized Scores

**Modify `retrieve_and_answer()` in `app.py`:**

```python
def retrieve_and_answer(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Enhanced retrieval that searches across text, tables, and images.
    Returns normalized relevance scores (0-1).
    """
    # 1. Embed query
    query_embedding = app_state.embedding_manager.embed_query(query)

    # 2. Search vector store (same as before)
    search_results = app_state.vector_store.similarity_search(
        query_embedding=query_embedding,
        k=max_results * 2  # Get more to allow filtering
    )

    if not search_results:
        return {
            'success': True,
            'answer': "No documents found. Please upload documents first.",
            'citations': [],
            'error': None
        }

    # 3. Normalize scores to 0-1 range
    # Cosine similarity already in [-1, 1], but typically [0, 1] for normalized vectors
    # We'll clip and rescale if needed
    for doc in search_results:
        score = doc.metadata.get('similarity_score', 0)
        # Ensure score is in [0, 1]
        normalized_score = max(0.0, min(1.0, score))
        doc.metadata['similarity_score'] = normalized_score

    # 4. Take top N
    top_results = search_results[:max_results]

    # 5. Prepare retrieved data
    retrieved_data = []
    for doc in top_results:
        retrieved_data.append({
            'content': doc.page_content,
            'metadata': doc.metadata,
            'similarity_score': doc.metadata['similarity_score']
        })

    # 6. Generate answer (same as before)
    generated_answer = app_state.answer_generator.generate(
        query=query,
        retrieved_results=retrieved_data,
        total_documents=len(app_state.uploaded_files)
    )

    # 7. Build enhanced citations
    citations = []
    for doc in top_results:
        meta = doc.metadata
        element_type = meta.get('element_type', 'text')

        citation = {
            'source_file': meta.get('filename', 'Unknown'),
            'page_number': meta.get('page_number', 'N/A'),
            'chunk_index': meta.get('chunk_index', 0),
            'similarity_score': meta.get('similarity_score', 0),
            'verbatim': doc.page_content[:300] + ('...' if len(doc.page_content) > 300 else ''),
            'full_text': doc.page_content,
            'source_type': element_type,
            'location': f"Page {meta.get('page_number')}, {element_type.title()}"
        }

        # Add type-specific fields
        if element_type == 'table':
            citation['is_table'] = True
            citation['markdown_table'] = doc.page_content
        elif element_type == 'image':
            citation['is_image'] = True
            citation['image_caption'] = meta.get('image_caption', '')
            citation['ocr_text'] = meta.get('ocr_text', '')
            # If we saved the image file, include URL
            if 'image_path' in meta:
                citation['image_url'] = f"/static/extracted_images/{meta['document_id']}_{meta['element_id']}.png"

        citations.append(citation)

    # 8. Build answer text (same as before, but can add type context)
    answer_text = generated_answer.answer_text

    if citations:
        answer_text += "\n\nSources:\n"
        for i, cite in enumerate(citations, 1):
            source_label = f"[{i}] {cite['source_file']} ({cite['location']})"
            answer_text += f"{source_label}\n"
            if cite['source_type'] == 'table':
                answer_text += f"    [TABLE] {cite['verbatim']}\n"
            elif cite['source_type'] == 'image':
                answer_text += f"    [IMAGE] {cite['verbatim']}\n"
            else:
                answer_text += f"    \"{cite['verbatim']}\"\n"

    return {
        'success': True,
        'answer': answer_text,
        'citations': citations,
        'answer_type': generated_answer.answer_type,
        'confidence': generated_answer.confidence
    }
```

---

## 3. Updated API Response Schema

```json
{
  "success": true,
  "answer": "Based on the documents...",
  "citations": [
    {
      "source_file": "paper.pdf",
      "page_number": 3,
      "chunk_index": 0,
      "similarity_score": 0.87,
      "verbatim": "The experimental results show...",
      "full_text": "Full content...",
      "source_type": "text",
      "location": "Page 3, Text"
    },
    {
      "source_file": "paper.pdf",
      "page_number": 5,
      "chunk_index": 12,
      "similarity_score": 0.82,
      "verbatim": "| Metric | Value |\n|--------|-------|\n| Accuracy | 94% |",
      "full_text": "Full table markdown...",
      "source_type": "table",
      "location": "Page 5, Table",
      "is_table": true,
      "markdown_table": "| Metric | Value |\n|--------|-------|\n| Accuracy | 94% |"
    },
    {
      "source_file": "paper.pdf",
      "page_number": 7,
      "chunk_index": 18,
      "similarity_score": 0.75,
      "verbatim": "A line graph showing accuracy over time...",
      "full_text": "Full description...",
      "source_type": "image",
      "location": "Page 7, Image",
      "is_image": true,
      "image_caption": "A line graph showing accuracy over time with three lines...",
      "ocr_text": "Accuracy: 94%\nPrecision: 91%",
      "image_url": "/static/extracted_images/doc123_img_005.png"
    }
  ],
  "answer_type": "found",
  "confidence": "high"
}
```

---

## 4. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Install `pymupdf` in requirements.txt
- [ ] Create `pdf_extractor.py` with PyMuPDF extraction
- [ ] Create `image_analyzer.py` with BLIP-2 + OCR
- [ ] Create `multimodal_chunker.py` with smart chunking
- [ ] Test extraction on sample PDFs with images/tables

### Phase 2: Integration
- [ ] Modify `app.py` to use new pipeline for PDFs
- [ ] Add image saving to `static/extracted_images/`
- [ ] Update `process_uploaded_file()` for PDFs
- [ ] Ensure metadata includes `element_type`, `bbox`, `element_id`
- [ ] Test embedding generation for all content types

### Phase 3: Retrieval Enhancement
- [ ] Verify vector search works across modalities
- [ ] Update `retrieve_and_answer()` with normalized scores
- [ ] Add type-specific citation fields
- [ ] Test queries: "What does the table on page 5 show?" → returns table

### Phase 4: Frontend Display
- [ ] Update `script.js` to render tables (Markdown → HTML)
- [ ] Add image display with `<img>` tags
- [ ] Add CSS for `.table-citation` and `.image-citation`
- [ ] Add badges: [TABLE], [IMAGE]
- [ ] Test responsive rendering

### Phase 5: Audio Extension (Parallel)
- [ ] Create `audio_processor.py` (as in previous plan)
- [ ] Add audio endpoints
- [ ] Integrate with vector store
- [ ] Frontend audio UI

---

## 5. Dependencies to Add

```txt
# requirements.txt additions
pymupdf>=1.23.0
transformers>=4.30.0
torch>=2.0.0
pillow>=9.0.0
# Optional: For better table extraction
camelot-py[cv]>=0.11.0  # Alternative table extraction
# OR
tabula-py>=2.8.0
```

---

## 6. Performance Considerations

- **BLIP-2 Model Size:** ~15GB (large). Consider:
  - Using smaller model: `Salesforce/blip2-flan-t5-xl` (~5GB)
  - Running on GPU for speed
  - Caching captions (don't re-analyze same image)
- **Image Storage:** Save extracted images to disk, not in vector store metadata
- **Batch Processing:** Process all images after PDF extraction, before chunking
- **Async:** Consider async image analysis for multiple images

---

## 7. Testing Strategy

1. **Unit Tests:**
   - PDF extraction returns correct number of elements
   - Image analysis produces non-empty caption
   - OCR extracts text from image with text

2. **Integration Tests:**
   - Upload PDF with 1 table + 2 images
   - Query "What does the table show?" → table returned
   - Query "Describe the images" → image captions returned
   - Verify citations have correct `element_type`

3. **End-to-End:**
   - Upload academic paper (with figures/tables)
   - Ask specific questions about visual content
   - Verify answer includes relevant visual element citations

---

## 8. Success Criteria

✅ All text, tables, and images extracted from PDFs  
✅ Each element has precise page number and bounding box  
✅ Image captions generated with BLIP-2  
✅ OCR text extracted from images  
✅ All content types searchable with semantic similarity  
✅ Citations clearly indicate source type (text/table/image)  
✅ Relevance scores normalized 0-1  
✅ Tables rendered as HTML in frontend  
✅ Images displayed with captions  
✅ System handles PDFs up to 50 pages in <60s

---

This specification provides a production-ready multimodal PDF processing pipeline that meets your requirements for robust visual content analysis and retrieval.