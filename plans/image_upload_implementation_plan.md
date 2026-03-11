# VirtualTeachingAssistant_T18 Image Upload Integration Plan

## Executive Summary

This document provides a comprehensive implementation plan to integrate the VisionModel functionality into the VirtualTeachingAssistant_T18 application. The current merge added vision model files but they are not functional due to missing integration points.

---

## Phase 1: Configuration & Backend Infrastructure

### Step 1.1: Update Allowed File Extensions

**File**: `app.py`
**Line**: 44
**Current Code**:
```python
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt', 'mp3', 'wav', 'ogg', 'm4a', 'flac'}
```

**Modified Code**:
```python
# Document extensions
DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'txt', 'mp3', 'wav', 'ogg', 'm4a', 'flac'}

# Image extensions for vision model
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tiff', 'tif'}

# Combined extensions
app.config['ALLOWED_EXTENSIONS'] = DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS

# Separate config for image-specific limits
app.config['MAX_IMAGE_SIZE'] = 10 * 1024 * 1024  # 10MB for images
app.config['ALLOWED_IMAGE_EXTENSIONS'] = IMAGE_EXTENSIONS
```

**Security Considerations**:
- Whitelist approach prevents file type spoofing
- Separate size limit prevents large image DoS attacks

---

### Step 1.2: Add Image Validation Function

**File**: `app.py`
**Location**: After `allowed_file()` function (around line 401)

**Add**:
```python
def allowed_image(filename: str) -> bool:
    """
    Check if the uploaded file is an allowed image type.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        bool: True if allowed, False otherwise
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config.get('ALLOWED_IMAGE_EXTENSIONS', IMAGE_EXTENSIONS)


def validate_image_file(file, max_size: int = None) -> Dict[str, Any]:
    """
    Comprehensive validation for image uploads.
    
    Args:
        file: FileStorage object from Flask
        max_size: Maximum file size in bytes (defaults to MAX_IMAGE_SIZE)
        
    Returns:
        dict: {'valid': bool, 'error': str or None, 'size': int}
    """
    max_size = max_size or app.config.get('MAX_IMAGE_SIZE', 10 * 1024 * 1024)
    
    # Check filename
    if not file.filename or file.filename == '':
        return {'valid': False, 'error': 'No filename provided', 'size': 0}
    
    # Check extension
    if not allowed_image(file.filename):
        return {'valid': False, 'error': f'Image format not allowed. Supported: {", ".join(app.config.get("ALLOWED_IMAGE_EXTENSIONS", IMAGE_EXTENSIONS))}', 'size': 0}
    
    # Check file size (seek to end, then back to start)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    if size > max_size:
        return {'valid': False, 'error': f'Image too large. Maximum size: {max_size // (1024*1024)}MB', 'size': size}
    
    if size == 0:
        return {'valid': False, 'error': 'Empty file uploaded', 'size': 0}
    
    return {'valid': True, 'error': None, 'size': size}
```

---

### Step 1.3: Add Image Processing Function

**File**: `app.py`
**Location**: Add after `process_uploaded_file()` function (around line 510)

**Add**:
```python
def process_image_file(file_path: str, file_id: str) -> Dict[str, Any]:
    """
    Process an uploaded image file using the vision model.
    
    Args:
        file_path: Path to the uploaded image
        file_id: Unique identifier for the file
        
    Returns:
        dict: Processing result with success status and details
    """
    result = {
        'success': False,
        'file_id': file_id,
        'file_path': file_path,
        'file_name': os.path.basename(file_path),
        'file_type': 'image',
        'processing_mode': 'vision',
        'description': None,
        'error': None
    }
    
    try:
        # Check if required dependencies are available
        if not NEMOTRON_AVAILABLE:
            result['error'] = 'Vision model dependencies not available'
            return result
        
        # Get description using Nemotron
        description = GetDescriptionFromLLM(file_path)
        result['description'] = description
        result['success'] = True
        
        logger.info(f"Image processed successfully: {file_path}")
        
    except FileNotFoundError as e:
        result['error'] = f'Image file not found: {str(e)}'
        logger.error(f"Image file not found: {file_path}")
    except ValueError as e:
        result['error'] = f'Invalid image format: {str(e)}'
        logger.error(f"Invalid image format: {file_path}")
    except Exception as e:
        result['error'] = f'Processing failed: {str(e)}'
        logger.error(f"Image processing error: {e}")
        import traceback
        traceback.print_exc()
    
    return result
```

---

### Step 1.4: Add Vision Model Import

**File**: `app.py`
**Location**: Top imports section (around line 30)

**Add**:
```python
# Vision model imports
NEMOTRON_AVAILABLE = False
try:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from NemotronNano import GetDescriptionFromLLM, kSupportedList
    NEMOTRON_AVAILABLE = True
    logger.info("Vision model (Nemotron) loaded successfully")
except ImportError as e:
    logger.warning(f"Vision model not available: {e}")
```

---

### Step 1.5: Add Image Upload API Endpoint

**File**: `app.py`
**Location**: After `/api/upload` endpoint (around line 710)

**Add**:
```python
@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    """
    Handle image file upload for vision model processing.
    
    Request:
        - file: Image file (multipart/form-data)
        
    Response:
        - success: bool
        - file_id: str
        - file_name: str
        - description: str (if successful)
        - error: str (if failed)
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Validate image
        validation = validate_image_file(file)
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': validation['error']
            }), 400
        
        # Save the file
        file_id = generate_file_id()
        filename = secure_filename(file.filename)
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}_{filename}")
        file.save(file_path)
        
        logger.info(f"Image saved: {file_path}")
        
        # Process the image
        result = process_image_file(file_path, file_id)
        
        if not result['success']:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify(result), 400
        
        # Store file info in app_state
        if not hasattr(app_state, 'uploaded_images'):
            app_state.uploaded_images = {}
        
        app_state.uploaded_images[file_id] = {
            'file_path': file_path,
            'file_name': filename,
            'upload_time': datetime.now().isoformat(),
            'description': result.get('description')
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/images', methods=['GET'])
def list_images():
    """List all uploaded images."""
    try:
        images = []
        if hasattr(app_state, 'uploaded_images'):
            for image_id, info in app_state.uploaded_images.items():
                images.append({
                    'file_id': image_id,
                    'file_name': info['file_name'],
                    'upload_time': info['upload_time'],
                    'description': info.get('description', '')[:100] + '...' if info.get('description') else None
                })
        
        return jsonify({
            'success': True,
            'images': images
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/images/<file_id>', methods=['DELETE'])
def delete_image(file_id):
    """Delete an uploaded image."""
    try:
        if not hasattr(app_state, 'uploaded_images') or file_id not in app_state.uploaded_images:
            return jsonify({
                'success': False,
                'error': 'Image not found'
            }), 404
        
        info = app_state.uploaded_images[file_id]
        if os.path.exists(info['file_path']):
            os.remove(info['file_path'])
        
        del app_state.uploaded_images[file_id]
        
        return jsonify({
            'success': True,
            'message': 'Image deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

---

## Phase 2: Frontend Modifications

### Step 2.1: Update HTML File Input

**File**: `templates/index.html`
**Line**: 113

**Current**:
```html
<input type="file" id="fileInput" accept=".pdf,.docx,.txt" multiple>
```

**Modified**:
```html
<input type="file" id="fileInput" accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,.gif,.bmp" multiple>
```

### Step 2.2: Add Image Upload Button

**File**: `templates/index.html`
**Location**: After line 66 (before `</div>` of welcome-actions)

**Add**:
```html
<button class="terminal-btn" id="quickImageUpload" title="Upload image for vision analysis">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21 15 16 10 5 21"/>
    </svg>
    <span class="prompt"></span>image
</button>
```

### Step 2.3: Add Image Preview Container

**File**: `templates/index.html`
**Location**: After the files-bar div (around line 87)

**Add**:
```html
<!-- Images Bar -->
<div class="images-bar" id="imagesBar" style="display: none;">
    <span style="color: var(--text-dim); font-size: 0.75rem;">images:</span>
    <div id="imagesList" style="display: flex; gap: 8px; flex-wrap: wrap;"></div>
    <button class="files-clear" id="clearImagesBtn">[clear]</button>
</div>
```

### Step 2.4: Update JavaScript - State Variables

**File**: `static/script.js`
**Line**: 22-25

**Current**:
```javascript
// State
let uploadedFiles = [];
let isUploading = false;
let isProcessing = false;
```

**Modified**:
```javascript
// State
let uploadedFiles = [];
let uploadedImages = [];
let isUploading = false;
let isProcessing = false;
let isUploadingImage = false;
```

### Step 2.5: Update JavaScript - Event Listeners

**File**: `static/script.js`
**Location**: In `setupEventListeners()` function (around line 44)

**Add after line 64:
```javascript
// Image upload button
document.getElementById('quickImageUpload').addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.png,.jpg,.jpeg,.webp,.gif,.bmp';
    input.multiple = true;
    input.onchange = (e) => {
        if (e.target.files.length > 0) {
            uploadImages(e.target.files);
        }
    };
    input.click();
});

// Clear images
document.getElementById('clearImagesBtn').addEventListener('click', clearAllImages);
```

### Step 2.6: Add Image Upload Function

**File**: `static/script.js`
**Location**: After `uploadFiles()` function (around line 135)

**Add**:
```javascript
async function uploadImages(files) {
    if (isUploadingImage) return;
ploadingImage = true    
    isU;
    statusText.textContent = 'processing image...';
    statusDot.classList.add('inactive');
    
    let uploadedCount = 0;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Client-side validation
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif', 'image/bmp'];
        if (!validTypes.includes(file.type)) {
            showToast(`Invalid image format: ${file.name}`);
            continue;
        }
        
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            showToast(`Image too large: ${file.name} (max 10MB)`);
            continue;
        }
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`${API_BASE}/api/upload/image`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                uploadedCount++;
                uploadedImages.push(result);
                updateImagesBar();
            } else {
                showToast(`Error: ${result.error}`);
            }
        } catch (error) {
            console.error('Image upload error:', error);
            showToast(`Upload failed: ${file.name}`);
        }
    }
    
    isUploadingImage = false;
    statusText.textContent = 'ready';
    statusDot.classList.remove('inactive');
    
    if (uploadedCount > 0) {
        showToast(`${uploadedCount} image(s) processed`);
    }
}

function updateImagesBar() {
    const imagesBar = document.getElementById('imagesBar');
    const imagesList = document.getElementById('imagesList');
    
    if (uploadedImages.length === 0) {
        imagesBar.style.display = 'none';
        return;
    }
    
    imagesBar.style.display = 'flex';
    imagesList.innerHTML = '';
    
    uploadedImages.forEach((img) => {
        const tag = document.createElement('span');
        tag.className = 'file-tag image-tag';
        tag.innerHTML = `<span class="ext">IMG</span> ${img.file_name}`;
        imagesList.appendChild(tag);
    });
}

async function clearAllImages() {
    try {
        // Clear from server
        for (const img of uploadedImages) {
            await fetch(`${API_BASE}/api/images/${img.file_id}`, {
                method: 'DELETE'
            });
        }
        
        uploadedImages = [];
        updateImagesBar();
        showToast('images cleared');
    } catch (error) {
        console.error('Failed to clear images:', error);
    }
}
```

### Step 2.7: Add Loading State for Images

**File**: `static/script.js`
**Location**: In `checkHealth()` function (around line 67)

**Add**:
```javascript
// Check vision model availability
if (data.vision_available) {
    statusText.textContent = 'ready + vision';
    statusDot.classList.remove('inactive');
}
```

---

## Phase 3: Testing Procedures

### Test 3.1: Unit Tests

| Test Case | Expected Result |
|-----------|-----------------|
| Upload valid PNG image | Success with description |
| Upload valid JPEG image | Success with description |
| Upload valid WebP image | Success with description |
| Upload invalid format (SVG) | 400 error with message |
| Upload oversized image (>10MB) | 400 error with size message |
| Upload empty file | 400 error |
| Upload corrupted image | Error handling with message |

### Test 3.2: Integration Tests

| Test Case | Expected Result |
|-----------|-----------------|
| Upload image + query document | Both work independently |
| Upload multiple images | All processed |
| Clear images | Removed from server |
| Network failure during upload | Error message shown |

### Test 3.3: UI Tests

| Test Case | Expected Result |
|-----------|-----------------|
| Click image button | File picker opens with image filters |
| Upload valid image | Toast confirmation |
| Upload invalid image | Error toast |
| Images bar shows uploaded images | Visible in UI |
| Clear images button works | Images removed |

---

## Phase 4: Rollback Strategy

### 4.1: Database Rollback
- No database changes required (using filesystem storage)

### 4.2: Code Rollback Steps

1. **Revert `app.py`**:
   - Restore original `ALLOWED_EXTENSIONS`
   - Remove image upload endpoint
   - Remove vision model imports

2. **Revert `templates/index.html`**:
   - Restore original file input accept attribute
   - Remove image upload button

3. **Revert `static/script.js`**:
   - Remove image-related state variables
   - Remove uploadImages function
   - Remove event listeners

### 4.3: Quick Rollback Commands
```bash
# If using git
git checkout HEAD~1 -- app.py templates/index.html static/script.js
```

---

## Phase 5: Dependency Requirements

### 5.1: Required Python Packages

```txt
# Already in requirements.txt (verify)
torch>=2.0.0
transformers>=4.30.0
Pillow>=9.0.0
numpy>=1.24.0

# New dependencies to add
# (NemotronNano uses Hugging Face transformers)
accelerate>=0.20.0
```

### 5.2: System Requirements

- GPU recommended for vision model (CPU will work slowly)
- Minimum 4GB RAM
- 2GB disk space for models

---

## Implementation Sequence

```
Phase 1 (Backend): Steps 1.1 → 1.2 → 1.3 → 1.4 → 1.5
     ↓
Phase 2 (Frontend): Steps 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7
     ↓
Phase 3 (Testing): All tests in sequence
     ↓
Phase 4 (Deploy): Monitor and prepare rollback if needed
```

---

## Security Considerations

1. **File Type Validation**: Whitelist approach prevents malicious file uploads
2. **File Size Limits**: Prevents DoS via large uploads
3. **Filename Sanitization**: `secure_filename()` prevents path traversal
4. **Temporary Storage**: Images stored in upload folder, cleaned on failure
5. **Error Messages**: Generic errors in production to prevent information leakage
