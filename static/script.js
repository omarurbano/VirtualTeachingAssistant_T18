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
let isUploading = false;
let isProcessing = false;

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupEventListeners();
    await checkHealth();
    await loadFiles();
    autoResizeTextarea();
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
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`${API_BASE}/api/upload`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                uploadedCount++;
                uploadedFiles.push(result);
                updateFilesBar();
            } else {
                console.error('Upload failed:', result.error);
            }
        } catch (error) {
            console.error('Upload error:', error);
        }
    }
    
    isUploading = false;
    statusText.textContent = 'ready';
    statusDot.classList.remove('inactive');
    
    if (uploadedCount > 0) {
        showToast(`${uploadedCount} file(s) loaded`);
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
        tag.innerHTML = `<span class="ext">${file.file_type}</span> ${file.file_name}`;
        filesList.appendChild(tag);
    });
}

async function loadFiles() {
    try {
        const response = await fetch(`${API_BASE}/api/files`);
        const data = await response.json();
        
        if (data.success && data.files.length > 0) {
            uploadedFiles = data.files;
            updateFilesBar();
        }
    } catch (error) {
        console.error('Failed to load files:', error);
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
  - upload: PDF, DOCX, TXT files
  - query: ask questions about document content
  - citations: sources shown with page numbers

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
    
    try {
        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: message, max_results: 5 })
        });
        
        const data = await response.json();
        
        loadingIndicator.classList.remove('active');
        
        if (data.success) {
            addMessageWithCitations('ai', data.answer, data.citations);
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
            
            html += `
                <div class="citation-item">
                    <div class="citation-header">
                        <span class="citation-source">[${index + 1}] ${escapeHtml(citation.source_file)}</span>
                        <span class="citation-match">${scorePercent}%</span>
                    </div>
                    <div class="citation-loc">${escapeHtml(citation.location)}</div>
                    <div class="citation-text">"${escapeHtml(citation.verbatim)}"</div>
                </div>
            `;
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
