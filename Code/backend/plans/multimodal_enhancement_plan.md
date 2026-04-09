# Multimodal Enhancement Plan
## Fixing PDF Image/Table Analysis & Audio Upload Extension

**Date:** 2025-03-10  
**Status:** Proposed Architecture  
**Author:** CPT_S 421 Development Team

---

## 1. Current State Analysis

### Existing PDF Processing Issues

**Problem:** The current `app.py` uses `SimpleDocumentProcessor` which relies on `PyPDFLoader` that only extracts **text**. It completely ignores:
- Images embedded in PDFs
- Tables with structured data
- OCR text from images
- Page-level metadata for citations

**Code Evidence:**
```python
# app.py - process_uploaded_file()
if file_ext == 'pdf':
    documents = app_state.document_processor.load_document(file_path)
    # This only gets text! No images, no tables.
```

**Impact:** Users upload academic papers/technical documents with figures and tables, but the system cannot answer questions about visual content.

### Current Audio Handling

**Problem:** Audio files are processed in `app.py` with a simple `process_audio_file()` function that:
- Uses Whisper if available
- Creates a single document with all transcribed text
- No chunking, no metadata, no page numbers
- Not integrated with the main document processor

**Code Evidence:**
```python
# app.py - process_uploaded_file() for audio
elif file_ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac']:
    audio_result = process_audio_file(file_path)
    if audio_result['success']:
        # Creates ONE document with all text, no chunking
        doc = TextDoc(text=audio_result['text'], metadata={...})
        documents = [doc]
```

---

## 2. Proposed Architecture

### Enhanced Multimodal PDF Processing

#### Solution: Integrate `multimodal_processor.py` into Main Pipeline

**Current State:** `multimodal_processor.py` exists but is NOT used by `app.py`. It's a standalone module with `MultimodalDocumentProcessor` that can extract:
- Text elements
- Tables (as structured data)
- Images (with optional OCR)
- Page numbers and coordinates

**Proposed Integration:**

```python
# NEW: Enhanced PDF processing in app.py

def process_pdf_with_multimodal(file_path: str, file_id: str) -> Dict[str, Any]:
    """
    Process PDF using multimodal extraction to capture text, tables, and images.
    Returns chunks with proper metadata for citations.
    """
    result = {
        'success': False,
        'file_id': file_id,
        'chunks_created': 0,
        'elements_extracted': {'text': 0, 'tables': 0, 'images': 0},
        'error': None
    }

    try:
        # 1. Initialize multimodal processor
        processor = MultimodalDocumentProcessor(
            extract_images=True,
            extract_tables=True,
            ocr_images=True,  # Extract text from images
            strategy='hi_res'  # Best quality
        )

        # 2. Extract all elements
        elements = processor.process_pdf(file_path)

        # 3. Convert elements to document chunks
        chunks = []
        for elem in elements:
            # Create LangChain Document with rich metadata
            doc = elem.to_langchain_document()

            # Add file-level metadata
            doc.metadata['document_id'] = file_id
            doc.metadata['filename'] = os.path.basename(file_path)
            doc.metadata['file_type'] = '.pdf'

            chunks.append(doc)

        # 4. Chunk the documents (if text is long)
        # Note: Tables and images may already be discrete chunks
        if chunks:
            # Use existing document processor's text splitter
            # But be careful: tables/images should stay intact
            final_chunks = smart_chunk_elements(chunks, chunk_size=1000, overlap=200)
        else:
            final_chunks = []

        # 5. Generate embeddings and add to vector store
        embeddings = app_state.embedding_manager.embed_documents(final_chunks)
        metadatas = [c.metadata for c in final_chunks]

        app_state.vector_store.add_documents(final_chunks, embeddings, metadatas)

        # 6. Count element types
        for elem in elements:
            if elem.element_type == 'text':
                result['elements_extracted']['text'] += 1
            elif elem.element_type == 'table':
                result['elements_extracted']['tables'] += 1
            elif elem.element_type == 'image':
                result['elements_extracted']['images'] += 1

        result['success'] = True
        result['chunks_created'] = len(final_chunks)

    except Exception as e:
        logger.error(f"Multimodal PDF processing error: {e}")
        result['error'] = str(e)

    return result
```

**Key Enhancement:** `smart_chunk_elements()` function that:
- Keeps tables as single chunks (don't split Markdown tables)
- Keeps images as single chunks (with OCR text)
- Only chunks long text elements
- Preserves page number and element type in metadata

#### Metadata Enrichment for Citations

**Add to chunk metadata:**
```python
{
    'document_id': file_id,
    'filename': 'paper.pdf',
    'file_type': '.pdf',
    'element_type': 'table',  # NEW: 'text', 'table', 'image', 'ocr'
    'page_number': 3,
    'chunk_index': 0,
    'element_id': 'elem_000123',  # From MultimodalElement
    'coordinates': (x1, y1, x2, y2),  # Position on page
    'caption': 'Table 1: Experimental results',  # If available
    'table_data': {...},  # Optional: structured table as JSON
    'image_path': '/uploads/...',  # Optional: path to extracted image
}
```

#### Query Answering with Visual Content

**Modify `retrieve_and_answer()` to handle multimodal results:**

```python
def retrieve_and_answer(query: str, max_results: int = 5) -> Dict[str, Any]:
    # ... existing embedding and search ...

    for doc in search_results:
        metadata = doc.metadata
        element_type = metadata.get('element_type', 'text')

        citation = {
            'source_file': metadata.get('filename', 'Unknown'),
            'page_number': metadata.get('page_number', 'N/A'),
            'chunk_index': metadata.get('chunk_index', 0),
            'similarity_score': metadata.get('similarity_score', 0),
            'verbatim': doc.page_content[:300],
            'full_text': doc.page_content,
            'source_type': element_type,  # 'text', 'table', 'image'
            'location': f"Page {metadata.get('page_number')}, {element_type}",
        }

        # Add type-specific fields
        if element_type == 'table':
            citation['is_table'] = True
            citation['markdown_table'] = doc.page_content  # Already in Markdown
        elif element_type == 'image':
            citation['is_image'] = True
            citation['ocr_text'] = metadata.get('ocr_text', '')
            # Optionally include image URL if served
            if 'image_path' in metadata:
                citation['image_url'] = f"/static/extracted/{os.path.basename(metadata['image_path'])}"

        citations.append(citation)
```

**Frontend Display Enhancement:**
```javascript
// In script.js - addMessageWithCitations()
citations.forEach((citation, index) => {
    let html = '';

    if (citation.source_type === 'table') {
        html = `
            <div class="citation-item table-citation">
                <div class="citation-header">
                    <span class="citation-source">[${index+1}] ${escapeHtml(citation.source_file)}</span>
                    <span class="citation-type">TABLE</span>
                </div>
                <div class="citation-loc">${escapeHtml(citation.location)}</div>
                <div class="table-container">
                    ${citation.verbatim} <!-- Markdown table -->
                </div>
            </div>
        `;
    } else if (citation.source_type === 'image') {
        html = `
            <div class="citation-item image-citation">
                <div class="citation-header">
                    <span class="citation-source">[${index+1}] ${escapeHtml(citation.source_file)}</span>
                    <span class="citation-type">IMAGE</span>
                </div>
                <div class="citation-loc">${escapeHtml(citation.location)}</div>
                <div class="image-preview">
                    <img src="${citation.image_url}" alt="Referenced image" />
                </div>
                <div class="citation-text">OCR: "${escapeHtml(citation.ocr_text)}"</div>
            </div>
        `;
    } else {
        // Standard text citation
        html = `...`;
    }
});
```

**CSS Additions:**
```css
/* Table citations */
.table-container {
    background: var(--bg-elevated);
    padding: 12px;
    border-radius: var(--radius-sm);
    overflow-x: auto;
    margin-top: 8px;
}

.table-container table {
    border-collapse: collapse;
    width: 100%;
}

.table-container th, .table-container td {
    border: 1px solid var(--border-subtle);
    padding: 6px 10px;
    text-align: left;
    font-family: var(--font-mono);
    font-size: 0.75rem;
}

/* Image citations */
.image-preview {
    margin-top: 8px;
    text-align: center;
}

.image-preview img {
    max-width: 100%;
    max-height: 200px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    object-fit: contain;
}

.citation-type {
    background: var(--accent-primary);
    color: var(--bg-deep);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.65rem;
    font-weight: 600;
}
```

---

### Audio Upload Extension

#### Current State
Audio files are processed but not integrated properly:
- No dedicated upload endpoint (uses `/api/upload`)
- No separate audio listing/management
- No transcription quality feedback
- No support for multiple audio files with proper chunking

#### Proposed Audio Module: `audio_processor.py`

```python
"""
Audio Processor Module
Handles audio file uploads, transcription with Whisper, and chunking.
"""

import os
import json
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AudioProcessor:
    """
    Processes audio files using Whisper for transcription.
    Supports: MP3, WAV, OGG, M4A, FLAC
    """

    def __init__(self, model_name: str = 'base', chunk_interval: int = 30):
        """
        Args:
            model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
            chunk_interval: Seconds per chunk for long audio (default 30s)
        """
        self.model_name = model_name
        self.chunk_interval = chunk_interval
        self.model = None
        self.is_available = False

        self._check_whisper_availability()

    def _check_whisper_availability(self):
        """Check if whisper is installed."""
        try:
            import whisper
            self.model = whisper.load_model(self.model_name)
            self.is_available = True
            logger.info(f"Whisper loaded: {self.model_name}")
        except ImportError:
            logger.warning("whisper not installed. Audio processing disabled.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe audio file to text.

        Returns:
            {
                'success': bool,
                'text': str,  # Full transcription
                'segments': List[Dict],  # Timestamped segments
                'language': str,
                'duration': float,
                'error': str | None
            }
        """
        if not self.is_available:
            return {'success': False, 'error': 'Whisper not available'}

        try:
            logger.info(f"Transcribing: {audio_path}")

            # Load audio and transcribe
            result = self.model.transcribe(
                audio_path,
                fp16=False,  # Use FP32 for CPU
                language='en',  # Auto-detect if None
                task='transcribe',
                verbose=False
            )

            return {
                'success': True,
                'text': result['text'],
                'segments': result['segments'],  # List of {start, end, text}
                'language': result.get('language', 'en'),
                'duration': result.get('duration', 0),
                'error': None
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {'success': False, 'error': str(e)}

    def create_chunks(self, transcription: Dict, file_id: str, filename: str) -> List[Dict]:
        """
        Convert transcription into document chunks with timestamps.

        Args:
            transcription: Result from transcribe()
            file_id: Unique file identifier
            filename: Original filename

        Returns:
            List of chunk dicts with metadata
        """
        chunks = []

        if not transcription['success']:
            return chunks

        segments = transcription.get('segments', [])
        full_text = transcription['text']

        # Option 1: Use segments as chunks (preserves timing)
        for i, segment in enumerate(segments):
            chunk = {
                'page_content': segment['text'].strip(),
                'metadata': {
                    'document_id': file_id,
                    'filename': filename,
                    'file_type': '.audio',
                    'chunk_index': i,
                    'source_type': 'audio',
                    'segment_start': segment['start'],
                    'segment_end': segment['end'],
                    'duration': segment['end'] - segment['start'],
                    'total_segments': len(segments)
                }
            }
            chunks.append(chunk)

        # Option 2: If no segments (older Whisper), chunk by character
        # (Would need to implement similar to SimpleDocumentProcessor)

        return chunks


class AudioFileManager:
    """Manages uploaded audio files metadata."""

    def __init__(self):
        self.audio_files = {}  # file_id -> metadata

    def register(self, file_id: str, filename: str, file_path: str,
                 transcription: Dict) -> Dict:
        """Register an uploaded audio file."""
        metadata = {
            'file_id': file_id,
            'filename': filename,
            'file_path': file_path,
            'upload_time': datetime.now().isoformat(),
            'transcription_success': transcription['success'],
            'transcription_text': transcription.get('text', ''),
            'segments_count': len(transcription.get('segments', [])),
            'duration': transcription.get('duration', 0),
            'language': transcription.get('language', 'unknown'),
            'error': transcription.get('error')
        }

        self.audio_files[file_id] = metadata
        return metadata

    def get(self, file_id: str) -> Dict | None:
        return self.audio_files.get(file_id)

    def list_all(self) -> List[Dict]:
        return list(self.audio_files.values())

    def delete(self, file_id: str) -> bool:
        if file_id in self.audio_files:
            del self.audio_files[file_id]
            return True
        return False
```

#### New API Endpoints for Audio

```python
# In app.py

# Initialize
audio_processor = AudioProcessor(model_name='base')
audio_manager = AudioFileManager()

@app.route('/api/audio/upload', methods=['POST'])
def upload_audio():
    """Dedicated audio upload endpoint."""
    try:
        if not audio_processor.is_available:
            return jsonify({
                'success': False,
                'error': 'Audio transcription not available. Install openai-whisper'
            }), 503  # Service Unavailable

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Validate extension
        allowed_audio = {'mp3', 'wav', 'ogg', 'm4a', 'flac'}
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_audio:
            return jsonify({
                'success': False,
                'error': f'Audio format not allowed. Use: {", ".join(allowed_audio)}'
            }), 400

        # Save file
        file_id = generate_file_id()
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)

        # Transcribe
        transcription = audio_processor.transcribe(file_path)

        # Register metadata
        audio_metadata = audio_manager.register(
            file_id, filename, file_path, transcription
        )

        # If transcription succeeded, create chunks and add to vector store
        if transcription['success']:
            chunks = audio_processor.create_chunks(transcription, file_id, filename)

            if chunks:
                # Generate embeddings
                embeddings = app_state.embedding_manager.embed_documents(chunks)
                metadatas = [c['metadata'] for c in chunks]
                contents = [c['page_content'] for c in chunks]

                # Add to vector store (need Document objects)
                from langchain.schema import Document
                documents = [
                    Document(page_content=content, metadata=meta)
                    for content, meta in zip(contents, metadatas)
                ]

                app_state.vector_store.add_documents(
                    documents,
                    embeddings,
                    metadatas
                )

                audio_metadata['chunks_created'] = len(chunks)
            else:
                audio_metadata['chunks_created'] = 0

        return jsonify({
            'success': transcription['success'],
            'file_id': file_id,
            'filename': filename,
            'transcription': transcription.get('text', '')[:500] + '...' if transcription.get('text') else None,
            'segments': len(transcription.get('segments', [])),
            'duration': transcription.get('duration', 0),
            'language': transcription.get('language'),
            'error': transcription.get('error'),
            'chunks_created': audio_metadata.get('chunks_created', 0)
        })

    except Exception as e:
        logger.error(f"Audio upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio', methods=['GET'])
def list_audio():
    """List all uploaded audio files."""
    try:
        audio_files = audio_manager.list_all()
        return jsonify({
            'success': True,
            'audio_files': [
                {
                    'file_id': af['file_id'],
                    'filename': af['filename'],
                    'upload_time': af['upload_time'],
                    'duration': af['duration'],
                    'segments': af['segments_count'],
                    'language': af['language'],
                    'has_transcription': af['transcription_success']
                }
                for af in audio_files
            ],
            'total': len(audio_files)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/<file_id>', methods=['DELETE'])
def delete_audio(file_id):
    """Delete an audio file and its transcription."""
    try:
        metadata = audio_manager.get(file_id)
        if not metadata:
            return jsonify({'success': False, 'error': 'Audio not found'}), 404

        # Delete file
        if os.path.exists(metadata['file_path']):
            os.remove(metadata['file_path'])

        # Remove from manager
        audio_manager.delete(file_id)

        # TODO: Remove chunks from vector store (need to implement filter)

        return jsonify({'success': True, 'message': 'Audio deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Frontend Audio Upload UI

**Add to `index.html`:**
```html
<!-- Add to quick-actions in welcome screen -->
<button class="terminal-btn" id="quickAudioUpload" title="Upload audio for transcription">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
    <span class="prompt"></span>audio
</button>
```

**Add to `script.js`:**
```javascript
// Add to DOM elements
const quickAudioUpload = document.getElementById('quickAudioUpload');

// Add to setupEventListeners()
quickAudioUpload.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.mp3,.wav,.ogg,.m4a,.flac';
    input.onchange = (e) => {
        if (e.target.files.length > 0) {
            uploadAudio(e.target.files);
        }
    };
    input.click();
});

// Add audio upload function
async function uploadAudio(files) {
    if (isUploading) return;

    isUploading = true;
    statusText.textContent = 'uploading audio...';
    statusDot.classList.add('inactive');

    for (const file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const toast = showToast(`Transcribing ${file.name}... (this may take a moment)`);

            const response = await fetch(`${API_BASE}/api/audio/upload`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                uploadedFiles.push(result);
                updateFilesBar();
                showToast(`Audio transcribed: ${file.name} (${result.duration}s)`);
            } else {
                showToast(`Audio failed: ${result.error}`);
            }
        } catch (error) {
            showToast(`Upload error: ${error.message}`);
        }
    }

    isUploading = false;
    statusText.textContent = 'ready';
    statusDot.classList.remove('inactive');
}

// Add audio bar to HTML (similar to filesBar and imagesBar)
<div class="audio-bar" id="audioBar" style="display: none;">
    <span style="color: var(--text-dim); font-size: 0.75rem;">audio:</span>
    <div id="audioList" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
    <button class="files-clear" id="clearAudioBtn">[clear]</button>
</div>
```

---

## 3. Implementation Roadmap

### Phase 1: Fix PDF Multimodal Processing (Priority: HIGH)

**Tasks:**
1. ✅ `multimodal_processor.py` already exists - needs testing
2. Create `smart_chunk_elements()` function in `app.py` or new module
3. Modify `process_uploaded_file()` to detect PDF and use multimodal processor
4. Add fallback to text-only if multimodal fails
5. Update vector store to preserve element_type metadata
6. Test with PDFs containing tables and images

**Expected Outcome:** PDFs with tables/figures are properly extracted and searchable.

### Phase 2: Query Answering with Visual Content (Priority: HIGH)

**Tasks:**
1. Modify `retrieve_and_answer()` to preserve `element_type` in citations
2. Update citation building to include type-specific fields
3. Enhance frontend `addMessageWithCitations()` to render tables/images
4. Add CSS for table and image citation display
5. Test: Ask "What does Table 1 show?" → returns actual table

**Expected Outcome:** Users see tables as rendered Markdown and images with OCR preview.

### Phase 3: Audio Upload Extension (Priority: MEDIUM)

**Tasks:**
1. Create `audio_processor.py` module (as specified above)
2. Add `audio_processor` and `audio_manager` to `app.py` global state
3. Implement `/api/audio/upload`, `/api/audio`, `/api/audio/<id>` endpoints
4. Add audio transcription chunking and vector store integration
5. Update frontend with audio upload button and audio bar
6. Test with various audio formats

**Expected Outcome:** Dedicated audio upload with proper transcription and search.

### Phase 4: Integration & Testing (Priority: MEDIUM)

**Tasks:**
1. Ensure all file types (PDF, DOCX, TXT, Audio, Images) work together
2. Test mixed queries: "From the PDF table and the audio, what are the key findings?"
3. Verify citations correctly reference source type
4. Performance testing with large multimodal PDFs
5. Error handling and user feedback

**Expected Outcome:** Robust, production-ready multimodal RAG system.

### Phase 5: Polish & Documentation (Priority: LOW)

**Tasks:**
1. Update README.md with new features
2. Add example PDFs with tables/images to test suite
3. Document API changes
4. Add configuration options (chunk size per type, OCR toggle, etc.)
5. Create user guide for multimodal features

---

## 4. Technical Considerations

### Table Extraction Quality
- **Challenge:** Tables in PDFs are notoriously difficult
- **Solution:** Use `unstructured` with `hi_res` strategy and `pdf2image` + OCR fallback
- **Metadata:** Preserve table structure as Markdown; also store raw JSON if needed

### Image Storage and Serving
- **Current:** Images extracted by `unstructured` are in-memory bytes
- **Option 1:** Save to `static/extracted/` and serve via Flask
- **Option 2:** Store as base64 in vector store metadata (increases size)
- **Recommendation:** Save to disk with `file_id_elementid.jpg` naming

### Audio Chunking Strategy
- **Whisper segments** already provide time-based chunks (natural breaks)
- **Alternative:** Fixed 30-second chunks for very long audio
- **Metadata:** Include timestamps for each chunk to enable "jump to audio" feature

### Vector Store Schema Changes
**New metadata fields:**
- `element_type`: 'text' | 'table' | 'image' | 'ocr'
- `element_id`: Unique element identifier
- `coordinates`: Bounding box (for PDFs)
- `caption`: Associated caption text
- `segment_start`, `segment_end`: For audio
- `ocr_text`: For images (separate from main content)

**Backward Compatibility:** Old chunks without these fields default to `element_type='text'`.

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `unstructured` fails on some PDFs | Medium | High | Fallback to PyPDFLoader, log warnings |
| Large PDFs cause memory issues | Medium | Medium | Implement streaming/chunked processing |
| Image OCR is slow or inaccurate | Medium | Medium | Cache OCR results, allow timeout |
| Audio transcription quality varies | Low | Low | Let users know it's best-effort |
| Vector store bloated with image metadata | Low | Medium | Don't store full image bytes, use file references |
| Frontend table rendering breaks Markdown | Low | Low | Sanitize table HTML, test with complex tables |

---

## 6. Success Metrics

- **PDF Multimodal:** Can correctly answer "What is in Table 2?" by returning the actual table
- **Image Queries:** Can answer "What does Figure 3 show?" by returning OCR text + image preview
- **Audio Search:** Can search transcribed audio content with proper timestamps
- **Performance:** PDF processing < 30s for 50-page doc, query latency < 5s
- **Accuracy:** Table extraction > 90% structural integrity

---

## 7. Implementation Checklist

### PDF/Image/Table
- [ ] Implement `smart_chunk_elements()` in `app.py`
- [ ] Modify `process_uploaded_file()` to use multimodal for PDFs
- [ ] Add `element_type` to chunk metadata
- [ ] Update `retrieve_and_answer()` citation building
- [ ] Add table/image CSS classes to `style.css`
- [ ] Update `script.js` to render tables and images
- [ ] Test with sample PDF containing tables and images

### Audio
- [ ] Create `audio_processor.py` module
- [ ] Add `audio_processor` and `audio_manager` to `app.py`
- [ ] Implement `/api/audio/upload` endpoint
- [ ] Implement `/api/audio` and `/api/audio/<id>` endpoints
- [ ] Add audio transcription chunking
- [ ] Integrate audio chunks into vector store
- [ ] Add audio UI to `index.html` and `script.js`
- [ ] Test with sample audio files

### Integration
- [ ] Verify all file types work together
- [ ] Test mixed queries
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Update documentation

---

## Conclusion

This plan addresses the core gaps in multimodal processing and audio support. The foundation (`multimodal_processor.py`) already exists but is unused—integration is straightforward. The audio module is new but follows existing patterns.

**Estimated Effort:**
- Phase 1 (PDF multimodal): 4-6 hours
- Phase 2 (Frontend display): 2-3 hours
- Phase 3 (Audio extension): 6-8 hours
- Phase 4 (Testing): 2-3 hours
- **Total:** 14-20 hours of development time

**Next Steps:**
1. Get approval on this plan
2. Switch to Code mode to implement changes
3. Test incrementally after each phase
4. Update teammate working on audio with this specification
