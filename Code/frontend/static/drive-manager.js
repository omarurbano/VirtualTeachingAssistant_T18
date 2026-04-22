// Google Drive Manager for VTA
// Handles OAuth flow and file selection in the course page

class DriveManager {
    constructor(courseId) {
        this.courseId = courseId;
        this.folderId = null;
        this.files = [];
        this.selectedFiles = new Set();
        this.accessToken = null;
    }

    // Start OAuth flow - redirect to Google
    async connect() {
        try {
            const response = await fetch(`/drive/auth?course_id=${this.courseId}`);
            
            if (response.redirected) {
                // Redirect to Google
                window.location.href = response.url;
            } else {
                const data = await response.json();
                if (data.url) {
                    window.location.href = data.url;
                } else {
                    alert('Error: ' + (data.error || 'Failed to start OAuth'));
                }
            }
        } catch (err) {
            console.error('Connect error:', err);
            alert('Failed to connect to Google Drive');
        }
    }

    // Load files from connected Drive
    async loadFiles(folderId) {
        if (!folderId) {
            console.error('No folder ID provided');
            return;
        }

        this.folderId = folderId;

        try {
            const response = await fetch(`/drive/list/${this.courseId}?folder_id=${folderId}`);
            
            if (response.ok) {
                const data = await response.json();
                // Handle both old format (files array) and new format (categorized)
                if (data.files) {
                    // Old format
                    this.files = data.files || [];
                } else if (data.all) {
                    // New format with categorization
                    this.files = data.all || [];
                    this.categorized = {
                        documents: data.documents || [],
                        videos: data.videos || [],
                        audio: data.audio || []
                    };
                    this.counts = data.counts || { documents: 0, videos: 0, audio: 0, total: 0 };
                }
                this.renderFileList();
            } else {
                const data = await response.json();
                console.error('Load files error:', data.error);
            }
        } catch (err) {
            console.error('Load files error:', err);
        }
    }

    // Toggle file selection
    toggleFile(fileId) {
        if (this.selectedFiles.has(fileId)) {
            this.selectedFiles.delete(fileId);
        } else {
            this.selectedFiles.add(fileId);
        }
        this.renderFileList();
    }

    // Get selected file info
    getSelectedFiles() {
        return this.files.filter(f => this.selectedFiles.has(f.id));
    }

    // Download and vectorize selected files
    async embedSelected() {
        const selected = this.getSelectedFiles();
        
        if (selected.length === 0) {
            alert('Please select at least one file to embed');
            return;
        }

        const results = [];
        
        for (const file of selected) {
            try {
                const mimeType = file.mimeType || file.type;
                const isVideo = mimeType.startsWith('video/');
                const isAudio = mimeType.startsWith('audio/');
                const isMediaFile = isVideo || isAudio;
                
                // Choose endpoint based on file type
                const endpoint = isMediaFile ? '/drive/media/embed' : '/drive/embed';
                const statusText = isMediaFile 
                    ? `Transcribing ${file.name}...` 
                    : `Embedding ${file.name}...`;
                
                document.getElementById('driveStatus').textContent = statusText;
                
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_id: file.id,
                        file_name: file.name,
                        mime_type: mimeType,
                        course_id: this.courseId
                    })
                });
                
                const data = await response.json();
                
                results.push({
                    name: file.name,
                    success: response.ok,
                    fileType: isMediaFile ? (isVideo ? 'video' : 'audio') : 'document',
                    duration: data.duration_seconds || null,
                    wordCount: data.word_count || null,
                    transcript: data.transcript || null,
                    error: data.error
                });
            } catch (err) {
                results.push({
                    name: file.name,
                    success: false,
                    error: err.message
                });
            }
        }

        return results;
    }
    
    // Get file type
    getFileTypeLabel(mimeType) {
        if (!mimeType) return 'File';
        
        if (mimeType.includes('pdf')) return 'PDF';
        if (mimeType.includes('document')) return 'Doc';
        if (mimeType.includes('spreadsheet')) return 'Sheet';
        if (mimeType.includes('presentation')) return 'Slide';
        if (mimeType.startsWith('video/')) return 'Video';
        if (mimeType.startsWith('audio/')) return 'Audio';
        return 'File';
    }

    // Render file list in the UI
    renderFileList() {
        const container = document.getElementById('driveFileList');
        if (!container) return;

        if (this.files.length === 0) {
            container.innerHTML = '<p class="text-dim">No files found in folder</p>';
            return;
        }

        container.innerHTML = this.files.map(file => `
            <div class="drive-file-item ${this.selectedFiles.has(file.id) ? 'selected' : ''}" 
                 data-file-id="${file.id}">
                <input type="checkbox" 
                       ${this.selectedFiles.has(file.id) ? 'checked' : ''}
                       onchange="driveManager.toggleFile('${file.id}')">
                <span class="file-icon">${this.getFileIcon(file.mimeType)}</span>
                <span class="file-name">${file.name}</span>
                <span class="file-type">${this.getFileTypeLabel(file.mimeType)}</span>
            </div>
        `).join('');
    }

    getFileIcon(mimeType) {
        if (!mimeType) return '📁';
        if (mimeType.includes('pdf')) return '📄';
        if (mimeType.includes('document')) return '📝';
        if (mimeType.includes('spreadsheet')) return '📊';
        if (mimeType.includes('presentation')) return '📽️';
        if (mimeType.startsWith('video/')) return '🎬';
        if (mimeType.startsWith('audio/')) return '🎧';
        return '📁';
    }

    formatDuration(seconds) {
        if (!seconds) return 'Unknown';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        if (mins >= 60) {
            const hours = Math.floor(mins / 60);
            const remainMins = mins % 60;
            return `${hours}:${remainMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    formatFileSize(bytes) {
        if (!bytes) return 'Unknown';
        const mb = bytes / (1024 * 1024);
        if (mb >= 1) {
            return `${mb.toFixed(1)} MB`;
        }
        const kb = bytes / 1024;
        return `${kb.toFixed(1)} KB`;
    }
}

// Global instance
let driveManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Get course ID from page
    const courseIdElement = document.getElementById('courseId');
    const courseId = courseIdElement ? courseIdElement.textContent : 'cpts451';
    
    driveManager = new DriveManager(courseId);
});

// Helper to show/hide Drive section
function showDriveSection() {
    const section = document.getElementById('driveFilesPanel');
    if (section) {
        section.style.display = 'block';
    }
}

function hideDriveSection() {
    const section = document.getElementById('driveFilesPanel');
    if (section) {
        section.style.display = 'none';
    }
}