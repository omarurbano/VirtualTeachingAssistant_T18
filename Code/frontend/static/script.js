// CPT_S 421 VTA - Document RAG System
// Terminal-style chat interface

const API_BASE = '';

// DOM Elements
const welcomeScreen = document.getElementById('welcomeScreen');
const chatMessages = document.getElementById('chatMessages');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const filesBar = document.getElementById('filesBar');
const filesList = document.getElementById('filesList');
const clearFilesBtn = document.getElementById('clearFilesBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const quickUpload = document.getElementById('quickUpload');
const quickHelp = document.getElementById('quickHelp');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

// State
let uploadedFiles = [];
let uploadedImages = [];
let isUploading = false;
let isProcessing = false;
let isUploadingImage = false;

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupEventListeners();
    await checkHealth();
    await loadFiles();
    await loadImages();
    autoResizeTextarea();
    
    // Check for course context in URL (student joined course)
    const urlParams = new URLSearchParams(window.location.search);
    let courseId = urlParams.get('course');
    
    console.log('URL params:', window.location.search, 'courseId:', courseId);
    
    // Fix: don't use the string "undefined"
    if (courseId === 'undefined' || !courseId) {
        courseId = null;
    }
    
    if (courseId) {
        window.currentCourseId = courseId;
        console.log('VTA initialized for course:', courseId);
        
        // Show course context in UI
        const statusText = document.getElementById('statusText');
        if (statusText) {
            statusText.textContent = `course: ${courseId}`;
        }
    }
}

function autoResizeTextarea() {
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });
}

function setupEventListeners() {
    // Enter to send
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Attach button
    attachBtn.addEventListener('click', () => fileInput.click());
    
    // File input
    fileInput.addEventListener('change', handleFileSelect);
    
    // Quick actions
    quickUpload.addEventListener('click', () => fileInput.click());
    quickHelp.addEventListener('click', showWelcomeMessage);
    
    // Clear files
    clearFilesBtn.addEventListener('click', clearAllDocuments);
    
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
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();
        
        if (data.sentence_transformers) {
            statusText.textContent = 'ready';
            statusDot.classList.remove('inactive');
        } else {
            statusText.textContent = 'fallback mode';
            statusDot.classList.add('inactive');
        }
    } catch (error) {
        statusText.textContent = 'error';
        statusDot.classList.add('inactive');
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFiles(files);
    }
    fileInput.value = '';
}

async function uploadFiles(files) {
    if (isUploading) return;
    
    isUploading = true;
    statusText.textContent = 'uploading...';
    statusDot.classList.add('inactive');
    
    let uploadedCount = 0;
    let failedCount = 0;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        try {
            const formData = new FormData();
            formData.append('file', file);

            // Add course_id if available
            const courseId = window.currentCourseId || new URLSearchParams(window.location.search).get('course');
            if (courseId) {
                formData.append('course_id', courseId);
            }

            console.log(`Uploading: ${file.name} (course: ${courseId || 'none'})`);

            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            console.log('Upload response:', result);
            
            if (result.success) {
                uploadedCount++;
                // Normalize the response to ensure consistent field names
                const normalizedFile = {
                    file_id: result.file_id,
                    file_name: result.file_name || result.filename || file.name,
                    file_type: (result.file_type || '?').replace('.', ''),
                    chunks: result.chunks_created || 0
                };
                uploadedFiles.push(normalizedFile);
                updateFilesBar();
            } else {
                failedCount++;
                console.error('Upload failed:', result.error);
                showToast(`Upload failed: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            failedCount++;
            console.error('Upload error:', error);
            showToast(`Upload error: ${error.message}`);
        }
    }
    
    isUploading = false;
    statusText.textContent = 'ready';
    statusDot.classList.remove('inactive');
    
    if (uploadedCount > 0) {
        showToast(`${uploadedCount} file(s) loaded`);
    }
    if (failedCount > 0 && uploadedCount === 0) {
        showToast(`All ${failedCount} file(s) failed to upload`);
    }
}

function updateFilesBar() {
    if (uploadedFiles.length === 0) {
        filesBar.classList.remove('active');
        return;
    }
    
    filesBar.classList.add('active');
    filesList.innerHTML = '';
    
    uploadedFiles.forEach((file) => {
        const tag = document.createElement('span');
        tag.className = 'file-tag';
        // Handle both response formats: file_name (from upload) or filename (from /api/files)
        const fileName = file.file_name || file.filename || 'unknown';
        const fileType = file.file_type || '?';
        tag.innerHTML = `<span class="ext">${fileType}</span> ${fileName}`;
        filesList.appendChild(tag);
    });
}

async function uploadImages(files) {
    if (isUploadingImage) return;
    
    isUploadingImage = true;
    statusText.textContent = 'analyzing image...';
    statusDot.classList.add('inactive');
    
    let uploadedCount = 0;
    let failedCount = 0;
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // Client-side validation
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif', 'image/bmp'];
        if (!validTypes.includes(file.type)) {
            showToast(`Invalid image format: ${file.name}`);
            failedCount++;
            continue;
        }
        
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            showToast(`Image too large: ${file.name} (max 10MB)`);
            failedCount++;
            continue;
        }
        
        try {
            const formData = new FormData();
            formData.append('file', file);

            // Add course_id if available
            const courseId = window.currentCourseId || new URLSearchParams(window.location.search).get('course');
            if (courseId) {
                formData.append('course_id', courseId);
            }

            // Show a temporary "processing" indicator for this specific image
            const tempToast = showToast(`Analyzing ${file.name}... (this may take a few moments)`);

            const response = await fetch(`${API_BASE}/api/upload/image`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            // Always add to uploadedImages, even if analysis failed
            // The file is kept on the server and shown in UI
            uploadedCount++;
            uploadedImages.push(result);
            updateImagesBar();
            
            if (result.success) {
                showToast(`Image analyzed: ${file.name}`);
            } else {
                // Show detailed error message
                const errorMsg = result.error || 'Unknown error';
                let displayError = errorMsg;
                
                // Provide more user-friendly messages for common errors
                if (errorMsg.includes('timeout') || errorMsg.includes('504') || errorMsg.includes('timed out')) {
                    displayError = 'Image analysis timed out. The image was uploaded but could not be analyzed.';
                } else if (errorMsg.includes('API key') || errorMsg.includes('authentication')) {
                    displayError = 'Vision service authentication error.';
                } else if (errorMsg.includes('not available')) {
                    displayError = 'Vision model is not available.';
                }
                
                showToast(`Analysis issue: ${displayError}`);
                console.warn('Image analysis failed:', result.error);
            }
        } catch (error) {
            failedCount++;
            console.error('Image upload error:', error);
            showToast(`Upload failed: ${file.name} - ${error.message}`);
        }
    }
    
    isUploadingImage = false;
    statusText.textContent = 'ready';
    statusDot.classList.remove('inactive');
    
    if (uploadedCount > 0) {
        // Toast already shown per image
    } else if (failedCount > 0 && uploadedCount === 0) {
        showToast(`All ${failedCount} image(s) failed to analyze`);
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

async function loadFiles() {
    try {
        const response = await fetch(`${API_BASE}/api/files`);
        const data = await response.json();
        
        if (data.success && data.files && data.files.length > 0) {
            // Normalize files to have consistent field names
            uploadedFiles = data.files.map(file => ({
                file_id: file.file_id,
                file_name: file.file_name || file.filename,
                file_type: file.file_type,
                chunks: file.chunks || 0
            }));
            updateFilesBar();
        }
    } catch (error) {
        console.error('Failed to load files:', error);
    }
}

async function loadImages() {
    try {
        const response = await fetch(`${API_BASE}/api/images`);
        const data = await response.json();
        
        if (data.success && data.images && data.images.length > 0) {
            // Convert API response to the format expected by updateImagesBar
            uploadedImages = data.images.map(img => ({
                file_id: img.file_id,
                file_name: img.file_name,
                upload_time: img.upload_time,
                description: img.description,
                // Since the /api/images endpoint returns a truncated description,
                // we'll mark these as successfully loaded from server
                success: true 
            }));
            updateImagesBar();
        }
    } catch (error) {
        console.error('Failed to load images:', error);
    }
}

async function clearAllDocuments() {
    try {
        const response = await fetch(`${API_BASE}/api/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            uploadedFiles = [];
            updateFilesBar();
            addMessage('ai', '> all documents cleared. upload new files to continue.');
        }
    } catch (error) {
        console.error('Failed to clear:', error);
    }
}

function showWelcomeMessage() {
    addMessage('ai', `> welcome to CPT_S 421 VTA Document RAG

supported operations:
  - upload: PDF, DOCX, TXT, Images, Audio (MP3, WAV, M4A, OGG, FLAC...)
  - query: ask questions about document content
  - citations: sources shown with page numbers, timestamps, speakers

type your question below and press enter.`);
}

async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) return;
    if (isProcessing) return;
    
    isProcessing = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // Show chat
    welcomeScreen.style.display = 'none';
    chatMessages.style.display = 'block';
    
    // Add user message
    addMessage('user', message);
    
    // Show loading
    loadingIndicator.classList.add('active');
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Get course_id from URL or global variable
    const urlParams = new URLSearchParams(window.location.search);
    let courseId = urlParams.get('course') || window.currentCourseId || null;
    
    // Don't send undefined as string - send null instead
    if (courseId === 'undefined' || courseId === undefined || courseId === null || courseId === '') {
        courseId = null;
    }
    
    try {
        const bodyObj = { 
            question: message, 
            max_results: 5
        };
        // Only add course_id if it's valid
        if (courseId) {
            bodyObj.course_id = courseId;
        }
        
        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyObj)
        });
        
        const data = await response.json();
        
        loadingIndicator.classList.remove('active');
        
        if (data.success) {
            addMessageWithCitations('ai', data.answer, data.citations);
            // Show course context in system message if available
            if (courseId && !window.courseContextShown) {
                window.courseContextShown = true;
                addMessage('system', `> Answering from course: ${courseId}`);
            }
        } else {
            addMessage('ai', `> error: ${data.error}`);
        }
    } catch (error) {
        loadingIndicator.classList.remove('active');
        addMessage('ai', `> error: ${error.message}`);
    }
    
    isProcessing = false;
    messageInput.focus();
}

function addMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const prompt = type === 'user' ? 'you@localhost' : 'vta@rag';
    const promptClass = type === 'user' ? 'var(--accent-tertiary)' : 'var(--accent-secondary)';
    
    messageDiv.innerHTML = `
        <div class="message-prompt" style="color: ${promptClass}">${prompt}$</div>
        <div class="message-content">${escapeHtml(content)}</div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderTableCitation(citation, index, scorePercent) {
    const markdownTable = citation.markdown_table || citation.verbatim;
    const tableRows = citation.table_rows || 'N/A';
    const tableCols = citation.table_columns || 'N/A';

    // Check if this citation has a source URL for clicking
    const sourceUrl = citation.source_url || '';
    const clickableSource = sourceUrl ?
        `<a href="#" onclick="openCitation('${sourceUrl}'); return false;" class="citation-link">[${index + 1}] ${escapeHtml(citation.source_file)}</a>` :
        `<span class="citation-source">[${index + 1}] ${escapeHtml(citation.source_file)}</span>`;

    return `
        <div class="citation-item table-citation">
            <div class="citation-header">
                ${clickableSource}
                <span class="citation-type-badge table-badge">TABLE</span>
                <span class="citation-match">${scorePercent}%</span>
            </div>
            <div class="citation-loc">${escapeHtml(citation.location)} (${tableRows} rows × ${tableCols} cols)</div>
            <div class="citation-description">Table content:</div>
            <div class="table-container">${escapeHtml(markdownTable)}</div>
        </div>
    `;
}

function renderImageCitation(citation, index, scorePercent) {
    const imageUrl = citation.image_url || '';
    const caption = citation.image_caption || 'No caption available';
    const ocrText = citation.ocr_text || '';
    const hasText = citation.has_text;

    let imageHtml = '';
    if (imageUrl) {
        imageHtml = `<div class="image-preview"><img src="${escapeHtml(imageUrl)}" alt="Image from ${escapeHtml(citation.source_file)}" onerror="this.style.display='none'" /></div>`;
    }

    let ocrHtml = '';
    if (hasText && ocrText) {
        ocrHtml = `<div class="citation-ocr"><strong>OCR Text:</strong> "${escapeHtml(ocrText.substring(0, 200))}${ocrText.length > 200 ? '...' : ''}"</div>`;
    }

    // Check if this citation has a source URL for clicking
    const sourceUrl = citation.source_url || '';
    const clickableSource = sourceUrl ?
        `<a href="#" onclick="openCitation('${sourceUrl}'); return false;" class="citation-link">[${index + 1}] ${escapeHtml(citation.source_file)}</a>` :
        `<span class="citation-source">[${index + 1}] ${escapeHtml(citation.source_file)}</span>`;

    return `
        <div class="citation-item image-citation">
            <div class="citation-header">
                ${clickableSource}
                <span class="citation-type-badge image-badge">IMAGE</span>
                <span class="citation-match">${scorePercent}%</span>
            </div>
            <div class="citation-loc">${escapeHtml(citation.location)}</div>
            ${imageHtml}
            <div class="citation-caption"><strong>Description:</strong> ${escapeHtml(caption)}</div>
            ${ocrHtml}
        </div>
    `;
}

function renderAudioCitation(citation, index, scorePercent) {
    const speaker = citation.speaker || 'Unknown';
    const timestamp = citation.timestamp || '';
    const tone = citation.tone || 'neutral';
    const confidence = citation.transcription_confidence;
    const verbatim = citation.verbatim || '';

    let metaParts = [];
    if (timestamp) metaParts.push(`at ${escapeHtml(timestamp)}`);
    if (speaker && speaker !== 'Unknown') metaParts.push(escapeHtml(speaker));
    if (tone && tone !== 'neutral') metaParts.push(`tone: ${escapeHtml(tone)}`);
    if (confidence) metaParts.push(`confidence: ${(confidence * 100).toFixed(0)}%`);

    const metaStr = metaParts.length > 0 ? `<div class="citation-audio-meta">${metaParts.join(' | ')}</div>` : '';

    // Check if this citation has a source URL for clicking
    const sourceUrl = citation.source_url || '';
    const clickableSource = sourceUrl ?
        `<a href="#" onclick="openCitation('${sourceUrl}'); return false;" class="citation-link">[${index + 1}] ${escapeHtml(citation.source_file)}</a>` :
        `<span class="citation-source">[${index + 1}] ${escapeHtml(citation.source_file)}</span>`;

    return `
        <div class="citation-item audio-citation">
            <div class="citation-header">
                ${clickableSource}
                <span class="citation-type-badge audio-badge">AUDIO</span>
                <span class="citation-match">${scorePercent}%</span>
            </div>
            <div class="citation-loc">${escapeHtml(citation.location)}</div>
            ${metaStr}
            <div class="citation-text">"${escapeHtml(verbatim)}"</div>
        </div>
    `;
}

function addMessageWithCitations(type, content, citations = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const prompt = type === 'user' ? 'you@localhost' : 'vta@rag';
    const promptClass = type === 'user' ? 'var(--accent-tertiary)' : 'var(--accent-secondary)';
    
    let html = escapeHtml(content);
    
    if (citations && citations.length > 0) {
        html += '<div class="citations-container">';
        html += '<div class="citations-label">// sources:</div>';
        
        citations.forEach((citation, index) => {
            const scorePercent = (citation.similarity_score * 100).toFixed(0);
            const sourceType = citation.source_type || 'text';
            
            let citationHtml = '';
            
            // Type-specific rendering
            if (sourceType === 'table') {
                citationHtml = renderTableCitation(citation, index, scorePercent);
            } else if (sourceType === 'image') {
                citationHtml = renderImageCitation(citation, index, scorePercent);
            } else if (sourceType === 'audio') {
                citationHtml = renderAudioCitation(citation, index, scorePercent);
            } else {
                // Standard text citation
                // Check if this citation has a source URL for clicking
                const sourceUrl = citation.source_url || '';
                const clickableSource = sourceUrl ?
                    `<a href="#" onclick="openCitation('${sourceUrl}'); return false;" class="citation-link">[${index + 1}] ${escapeHtml(citation.source_file)}</a>` :
                    `<span class="citation-source">[${index + 1}] ${escapeHtml(citation.source_file)}</span>`;

                citationHtml = `
                    <div class="citation-item">
                        <div class="citation-header">
                            ${clickableSource}
                            <span class="citation-match">${scorePercent}%</span>
                        </div>
                        <div class="citation-loc">${escapeHtml(citation.location)}</div>
                        <div class="citation-text">"${escapeHtml(citation.verbatim)}"</div>
                    </div>
                `;
            }
            
            html += citationHtml;
        });
        
        html += '</div>';
    }
    
    messageDiv.innerHTML = `
        <div class="message-prompt" style="color: ${promptClass}">${prompt}$</div>
        <div class="message-content">${html}</div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function openCitation(sourceUrl) {
    // Open PDF viewer or media player based on citation URL
    if (!sourceUrl) {
        showToast("No source URL available for this citation");
        return;
    }

    try {
        // Parse the URL to determine what type of viewer to open
        const url = new URL(sourceUrl, window.location.origin);

        if (sourceUrl.includes('/pdf/view')) {
            // PDF viewer
            openPdfViewer(sourceUrl);
        } else if (sourceUrl.includes('/media/play')) {
            // Video/audio player
            openMediaPlayer(sourceUrl);
        } else {
            // Fallback: open in new tab
            window.open(sourceUrl, '_blank');
        }
    } catch (error) {
        console.error('Error parsing citation URL:', error);
        showToast("Error opening citation source");
    }
}

function openPdfViewer(sourceUrl) {
    // Open PDF viewer in a modal or new window
    // For now, open in new tab. In future, could implement modal viewer
    window.open(sourceUrl, '_blank');
    showToast("Opening PDF viewer...");
}

function openMediaPlayer(sourceUrl) {
    // Open video/audio player in a modal or new window
    // For now, open in new tab. In future, could implement embedded player
    window.open(sourceUrl, '_blank');
    showToast("Opening media player...");
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--bg-elevated);
        border: 1px solid var(--accent-primary);
        color: var(--accent-primary);
        padding: 10px 20px;
        border-radius: 4px;
        font-family: var(--font-mono);
        font-size: 0.8rem;
        z-index: 1000;
        animation: fadeIn 0.2s ease;
    `;
    toast.textContent = `> ${message}`;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 2500);
}
