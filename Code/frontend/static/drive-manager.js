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
                this.files = data.files || [];
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
                document.getElementById('driveStatus').textContent = 
                    `Embedding ${file.name}...`;
                
                const response = await fetch(`/drive/embed`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_id: file.id,
                        file_name: file.name,
                        mime_type: file.mimeType,
                        course_id: this.courseId
                    })
                });
                
                const data = await response.json();
                results.push({
                    name: file.name,
                    success: response.ok,
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
        if (mimeType.includes('pdf')) return '📄';
        if (mimeType.includes('document')) return '📝';
        if (mimeType.includes('spreadsheet')) return '📊';
        if (mimeType.includes('presentation')) return '📽️';
        return '📁';
    }

    getFileTypeLabel(mimeType) {
        if (mimeType.includes('pdf')) return 'PDF';
        if (mimeType.includes('document')) return 'Doc';
        if (mimeType.includes('spreadsheet')) return 'Sheet';
        if (mimeType.includes('presentation')) return 'Slide';
        return 'File';
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