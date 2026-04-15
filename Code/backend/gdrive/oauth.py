# Google Drive OAuth Integration Module
# 
# Full OAuth 2.0 flow for connecting Google Drive to VTA
# Teachers can link their Drive, select files, and vectorize them

import os
import json
import logging
import threading
from urllib.parse import urlencode
from flask import session, redirect, url_for, jsonify, request

logger = logging.getLogger(__name__)

# ============================================
# OAUTH CONFIGURATION
# ============================================

def get_drive_config():
    """Get Google Drive OAuth configuration from environment."""
    return {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        'redirect_uri': os.environ.get('GOOGLE_REDIRECT_URI', ''),
        'scopes': [
            'https://www.googleapis.com/auth/drive.readonly',
        ]
    }


def build_auth_url(state_token: str) -> str:
    """Build the Google OAuth consent URL."""
    config = get_drive_config()
    
    if not config['client_id']:
        return None
    
    params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': ' '.join(config['scopes']),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state_token,
    }
    
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access/refresh tokens."""
    import requests
    
    config = get_drive_config()
    
    if not config['client_id']:
        return {'error': 'Google OAuth not configured'}
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'redirect_uri': config['redirect_uri'],
        'grant_type': 'authorization_code',
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=30)
        
        if response.ok:
            return response.json()
        else:
            logger.error(f"Token exchange failed: {response.text}")
            return {'error': 'Token exchange failed'}
    except Exception as e:
        logger.error(f"Token exchange error: {e}")
        return {'error': str(e)}


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh access token using refresh token."""
    import requests
    
    config = get_drive_config()
    
    if not config['client_id']:
        return {'error': 'Google OAuth not configured'}
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'refresh_token': refresh_token,
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'grant_type': 'refresh_token',
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=30)
        
        if response.ok:
            return response.json()
        else:
            logger.error(f"Token refresh failed: {response.text}")
            return {'error': 'Token refresh failed'}
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return {'error': str(e)}


# ============================================
# DRIVE API CLIENT
# ============================================

class GoogleDriveClient:
    """Client for Google Drive API."""
    
    def __init__(self, access_token: str = None, refresh_token: str = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    def _get_headers(self):
        """Get authorization headers."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
    
    def list_folder_files(self, folder_id: str, page_size: int = 100):
        """List files in a Google Drive folder."""
        import requests
        
        # Supported MIME types for documents
        supported_mimes = [
            'application/pdf',
            'application/vnd.google-apps.document',
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.google-apps.presentation',
            'text/plain',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ]
        
        query = f"'{folder_id}' in parents and trashed=false"
        mime_query = ' or '.join([f"mimeType='{m}'" for m in supported_mimes])
        query = f"({query}) and ({mime_query})"
        
        params = {
            'q': query,
            'pageSize': page_size,
            'fields': 'files(id,name,mimeType,size,modifiedTime,iconLink)',
            'supportsAllDrives': True,
        }
        
        try:
            response = requests.get(
                'https://www.googleapis.com/drive/v3/files',
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.ok:
                return response.json().get('files', [])
            else:
                logger.error(f"List files failed: {response.text}")
                return []
        except Exception as e:
            logger.error(f"List files error: {e}")
            return []
    
    def get_file_metadata(self, file_id: str):
        """Get file metadata."""
        import requests
        
        params = {
            'fields': 'id,name,mimeType,size,modifiedTime',
            'supportsAllDrives': True,
        }
        
        try:
            response = requests.get(
                f'https://www.googleapis.com/drive/v3/files/{file_id}',
                params=params,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.ok:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Get metadata error: {e}")
            return None
    
    def download_file(self, file_id: str, mime_type: str) -> tuple:
        """Download file content.
        
        Returns:
            (content_bytes, filename, output_extension)
        """
        import requests
        from io import BytesIO
        
        # Export Google Docs to standard formats
        export_formats = {
            'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.google-apps.spreadsheet': 'text/csv',
            'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        }
        
        metadata = self.get_file_metadata(file_id)
        if not metadata:
            return None, None, None
        
        filename = metadata.get('name', 'document')
        
        # Determine if we need to export
        if mime_type in export_formats:
            export_mime = export_formats[mime_type]
            ext = '.docx' if 'document' in export_mime else '.csv' if 'spreadsheet' in export_mime else '.pptx'
            
            params = {
                'mimeType': export_mime,
                'supportsAllDrives': True,
            }
            
            url = f'https://www.googleapis.com/drive/v3/files/{file_id}/export'
        else:
            # Direct download for regular files
            url = f'https://www.googleapis.com/drive/v3/files/{file_id}'
            params = {
                'alt': 'media',
                'supportsAllDrives': True,
            }
            ext = '.pdf' if mime_type == 'application/pdf' else '.txt'
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=60,
                stream=True
            )
            
            if response.ok:
                content = response.content
                return content, filename, ext
            else:
                logger.error(f"Download failed: {response.status_code}")
                return None, None, None
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None, None, None


def create_drive_client(access_token: str, refresh_token: str = None) -> GoogleDriveClient:
    """Factory to create Drive client."""
    return GoogleDriveClient(access_token, refresh_token)


# ============================================
# FLASK ROUTES - OAuth Flow
# ============================================

def register_drive_oauth_routes(app):
    """Register all Drive OAuth routes with Flask app."""
    
    @app.route('/drive/auth')
    def drive_auth_start():
        """Start OAuth flow - redirect to Google."""
        try:
            # Get course_id from params
            course_id = request.args.get('course_id')
            
            if not course_id:
                return jsonify({'error': 'course_id required'}), 400
            
            # Generate state token
            import secrets
            state = secrets.token_urlsafe(32)
            
            # Store state in session for verification
            session['drive_oauth_state'] = state
            session['drive_oauth_course'] = course_id
            
            # Build auth URL
            auth_url = build_auth_url(state)
            
            if not auth_url:
                return jsonify({'error': 'Google OAuth not configured. Please set GOOGLE_CLIENT_ID in environment.'}), 500
            
            return redirect(auth_url)
            
        except Exception as e:
            logger.error(f"Auth start error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/drive/callback')
    def drive_auth_callback():
        """Handle OAuth callback from Google."""
        try:
            error = request.args.get('error')
            if error:
                return jsonify({'error': error}), 400
            
            code = request.args.get('code')
            state = request.args.get('state')
            
            # Verify state
            expected_state = session.get('drive_oauth_state')
            if state != expected_state:
                return jsonify({'error': 'Invalid state'}), 400
            
            course_id = session.get('drive_oauth_course')
            
            # Exchange code for tokens
            tokens = exchange_code_for_tokens(code)
            
            if 'error' in tokens:
                return jsonify({'error': tokens['error']}), 500
            
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            
            if not access_token:
                return jsonify({'error': 'No access token'}), 500
            
            # Store tokens in Supabase for this course
            import requests
            try:
                requests.post(
                    f"{NODE_API_URL}/api/drive/connect",
                    json={
                        'course_id': course_id,
                        'teacher_id': session.get('drive_oauth_teacher', ''),
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                    },
                    timeout=5
                )
            except:
                pass
            
            # Store in session temporarily
            session['drive_access_token'] = access_token
            session['drive_refresh_token'] = refresh_token
            
            # Clear OAuth state
            session.pop('drive_oauth_state', None)
            session.pop('drive_oauth_course', None)
            
            # Redirect to course page
            return redirect(f'/instructor/course/{course_id}')
            
        except Exception as e:
            logger.error(f"Auth callback error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/drive/list/<course_id>')
    def list_drive_files(course_id):
        """List files in Drive folder."""
        try:
            # Get access token from session or Supabase
            access_token = session.get('drive_access_token')
            refresh_token = session.get('drive_refresh_token')
            
            if not access_token:
                # Try from Supabase
                import requests
                try:
                    response = requests.get(f"{NODE_API_URL}/api/drive/{course_id}", timeout=5)
                    if response.ok:
                        data = response.json()
                        access_token = data.get('access_token')
                        refresh_token = data.get('refresh_token')
                except:
                    pass
            
            if not access_token:
                return jsonify({'error': 'Drive not connected', 'files': []}), 401
            
            # Get folder ID
            folder_id = request.args.get('folder_id')
            if not folder_id:
                return jsonify({'error': 'folder_id required'}), 400
            
            client = create_drive_client(access_token, refresh_token)
            files = client.list_folder_files(folder_id)
            
            return jsonify({'files': files})
            
        except Exception as e:
            logger.error(f"List files error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/drive/download/<course_id>', methods=['POST'])
    def download_drive_file(course_id):
        """Download and return file content."""
        try:
            data = request.get_json()
            file_id = data.get('file_id')
            file_mime = data.get('mime_type')
            
            if not file_id:
                return jsonify({'error': 'file_id required'}), 400
            
            access_token = session.get('drive_access_token')
            
            if not access_token:
                return jsonify({'error': 'Not authenticated'}), 401
            
            client = create_drive_client(access_token)
            content, filename, ext = client.download_file(file_id, file_mime)
            
            if content:
                return jsonify({
                    'success': True,
                    'content': content.decode('utf-8', errors='ignore')[:50000],  # First 50k chars
                    'filename': filename,
                    'extension': ext
                })
            return jsonify({'error': 'Download failed'}), 500
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            return jsonify({'error': str(e)}), 500

    return app