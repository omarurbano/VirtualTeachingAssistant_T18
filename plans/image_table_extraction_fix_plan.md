# Image and Table Extraction Fix Plan

## Problem Statement
User wants images and tables extracted from PDFs to be displayed in the references section when asked about them.

## Current Issues Identified

### Issue 1: Multimodal PDF Processing Disabled (Primary Blocker)
- **Location**: `app.py:75`
- **Problem**: `app.config['USE_MULTIMODAL_PDF'] = False`
- **Impact**: PDF image/table extraction is completely disabled
- **Fix**: Change to `True`

### Issue 2: Image Path Not in Chunk Metadata (Bug)
- **Location**: `multimodal_chunker.py:239-248`
- **Problem**: Even when images are saved, the `image_path` is not added to the chunk's metadata
- **Details**: 
  - `image_analyses[element_id]['image_path']` is set at line 408
  - But `create_chunks()` at line 239 only extracts: caption, ocr_text, has_text, etc.
  - Missing: `image_path` needs to be added to chunk metadata
- **Impact**: Citation cannot find the image file to display
- **Fix**: Add `'image_path': analysis.get('image_path', '')` to chunk metadata

## Code Flow Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│  process_pdf_multimodal()                                       │
│  ├─ create_chunks_from_pdf()                                    │
│  │  ├─ PyMuPDFExtractor extracts pages/text/tables/images      │
│  │  ├─ ImageAnalyzer BLIP-2 generates captions + OCR text       │
│  │  ├─ Save images to static/extracted_images/                 │
│  │  │  └─ image_analyses[element_id]['image_path'] = filepath  │
│  │  └─ MultimodalChunker.create_chunks()                         │
│  │     └─ chunk.metadata MISSING 'image_path' ❌               │
│  ├─ Add chunks to vector store                                 │
│  └─ Store in uploaded_files                                    │
├─────────────────────────────────────────────────────────────────┤
│  Query Processing                                               │
│  ├─ Search vector store                                         │
│  └─ Build citations                                             │
│     ├─ Text: content displayed                                 │
│     ├─ Table: markdown_table displayed ✓                       │
│     └─ Image: image_url looked up from metadata['image_path']  │
│        └─ MISSING ❌ -> No image displayed                      │
└─────────────────────────────────────────────────────────────────┘
```

## Required Fixes

### Fix 1: Enable Multimodal PDF Processing
**File**: `app.py`
**Line**: 75
**Change**:
```python
# FROM:
app.config['USE_MULTIMODAL_PDF'] = False

# TO:
app.config['USE_MULTIMODAL_PDF'] = True
```

### Fix 2: Add Image Path to Chunk Metadata
**File**: `multimodal_chunker.py`
**Line**: 239-248
**Change**:
```python
# FROM:
metadata={
    'image_caption': caption,
    'ocr_text': ocr_text,
    'has_text': analysis.get('has_text', False),
    'caption_success': analysis.get('caption_success', False),
    'ocr_success': analysis.get('ocr_success', False),
    'image_width': image.width,
    'image_height': image.height,
    'image_format': 'png'
}

# TO:
metadata={
    'image_caption': caption,
    'ocr_text': ocr_text,
    'has_text': analysis.get('has_text', False),
    'caption_success': analysis.get('caption_success', False),
    'ocr_success': analysis.get('ocr_success', False),
    'image_width': image.width,
    'image_height': image.height,
    'image_format': 'png',
    'image_path': analysis.get('image_path', '')  # ADD THIS LINE
}
```

## What Works Already (No Changes Needed)
- ✅ Table extraction: Markdown tables properly stored in content, converted to `markdown_table` in citations
- ✅ Table display in frontend: `renderTableCitation()` in script.js:437-468
- ✅ Image display in frontend: `renderImageCitation()` in script.js:471-499
- ✅ Citation building for images: Lines 1108-1117 in app.py (logic correct, just needs path)
- ✅ Direct image upload: `/api/upload/image` endpoint works
- ✅ Image extensions config: Already includes `{'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'tif'}`

## Verification Steps After Fix
1. Upload a PDF with images
2. Check API response shows `elements_extracted` with image counts
3. Ask a question about an image in the PDF
4. Verify image appears in citations with relevance score

## Summary
Only 2 small fixes needed:
1. Enable multimodal PDF processing
2. Pass image_path to chunk metadata

The rest of the infrastructure is already in place and working.