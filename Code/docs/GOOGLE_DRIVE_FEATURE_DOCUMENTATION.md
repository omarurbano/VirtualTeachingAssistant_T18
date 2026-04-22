# Google Drive Integration Feature Documentation

## Virtual Teaching Assistant (VTA) - Google Drive Feature for Teachers

---

## Overview

The Google Drive integration feature in the Virtual Teaching Assistant (VTA) system allows teachers to connect their Google Drive account to the platform, browse and select files from their Drive, and import those files into the VTA system. Once imported, the files are processed through the system's vectorization pipeline and converted into searchable embeddings that the VTA can use to answer student questions. This feature enables teachers to easily share their course materials with the VTA without manually uploading files one by one.

The entire workflow is designed with security and efficiency in mind. The VTA system does not store the original files from Google Drive. Instead, it extracts the text content from those files, breaks the content into smaller chunks, generates vector embeddings for each chunk, and stores only the embeddings and metadata in the database. The original files remain safely stored on the teacher's Google Drive. This approach ensures that the teacher's original documents are never duplicated or stored outside of their Google Drive, maintaining data integrity and reducing storage requirements on the VTA system.

---

## Who Can Use This Feature

The Google Drive integration feature is exclusively available to teachers. Students cannot access this feature. This design decision ensures that only authorized instructors can connect their Google Drive and import course materials into the VTA system. Students can view and search the materials that teachers have imported, but they cannot modify or add new materials through the Google Drive integration.

This role-based access control is enforced at the API level through middleware decorators. When a student attempts to access any of the Google Drive endpoints, the system returns a 403 Forbidden error indicating that teacher access is required. This security measure ensures that the feature is used only by authorized personnel.

---

## Prerequisites

Before teachers can use the Google Drive integration feature, certain configuration must be completed. First, the application administrator must set up a project in the Google Cloud Console and enable the Google Drive API. Second, the administrator must create OAuth 2.0 credentials for the application, including a Client ID and Client Secret. Third, the administrator must configure the authorized redirect URI to point to the VTA application's callback endpoint. Finally, the administrator must add the Google OAuth credentials to the application's environment variables file.

For the Google Cloud Console setup, the administrator navigates to the Google Cloud Console website and creates a new project. Once the project is created, the administrator enables the Google Drive API by searching for it in the API Library and clicking Enable. To create credentials, the administrator goes to the Credentials section under APIs & Services, clicks Create Credentials, and selects OAuth client ID. The application type is set to Web application, and the authorized redirect URI is configured as http://localhost:5000/drive/callback for local development or the production URL when deployed.

The OAuth credentials are stored in the application's environment variables file. The required variables include GOOGLE_CLIENT_ID (which ends with .apps.googleusercontent.com), GOOGLE_CLIENT_SECRET (a longer random string), and GOOGLE_REDIRECT_URI (the callback URL configured in the Google Cloud Console). These credentials are essential for the OAuth flow to work correctly.

---

## How the Feature Works

The Google Drive integration feature operates through a multi-step workflow that involves OAuth authentication, file browsing, file selection, and automatic vectorization. This section provides a detailed explanation of each step in the workflow.

### Step 1: Initiating the Connection

The workflow begins when a teacher wants to connect their Google Drive to the VTA system. In the course page under the Materials tab, the teacher locates the Google Drive section. The teacher enters the URL of the Google Drive folder they want to connect and clicks the "Link Drive Folder" button.

The VTA system extracts the folder ID from the provided URL. Google Drive folder URLs come in several formats, and the system is designed to handle all common formats. The extracted folder ID is stored in the database and associated with the course. This allows the system to remember which folder is connected to each course, so teachers do not need to re-enter the folder URL every time they want to access it.

### Step 2: OAuth Authentication Flow

If the teacher has not yet connected their Google Drive, or if they need to re-authenticate, the system initiates the OAuth 2.0 authentication flow. This is a secure standard protocol used by Google for authorizing third-party applications to access user data.

When the teacher clicks "Link Drive Folder" or "Sync from Drive," the system checks if valid OAuth tokens exist. If not, the system redirects the teacher's browser to the Google sign-in page. On this page, the teacher enters their Google credentials and reviews the permissions that the VTA application is requesting. The VTA application requests only read-only access to the teacher's Google Drive, which means it can view and download files but cannot modify or delete them.

After the teacher reviews the permissions and clicks "Allow," Google redirects the browser back to the VTA application's callback URL (/drive/callback) with an authorization code. The VTA system then exchanges this authorization code for access and refresh tokens. The access token is temporary and expires after one hour, while the refresh token is long-lived and can be used to obtain new access tokens without requiring the teacher to log in again.

These tokens are stored securely in the database associated with the course. The system uses the refresh token to automatically obtain new access tokens when needed, ensuring that the connection remains active without requiring the teacher to re-authenticate frequently.

### Step 3: Browsing Files in Google Drive

Once the Google Drive is connected and authenticated, the teacher can browse the files in their connected folder. When the teacher clicks the "Sync from Drive" button, the VTA system retrieves the list of files from the connected Google Drive folder.

The system queries the Google Drive API to list all files in the specified folder. The query filters to include only supported file types, excluding files that cannot be processed by the system. The supported file types include PDF documents, Google Docs, Google Sheets, Google Slides, Microsoft Word documents, and plain text files.

The retrieved file list is displayed to the teacher in the course page. Each file is shown with its name, type icon, and a checkbox for selection. The teacher can review the available files and select the ones they want to import into the VTA system.

### Step 4: Importing Selected Files

After selecting the desired files, the teacher clicks the "Import Selected" button. The VTA system then begins processing each selected file individually.

For each file, the system performs the following operations. First, the system downloads the file from Google Drive to a temporary location on the server. For Google Docs, Google Sheets, and Google Slides, the system automatically converts them to standard formats (DOCX, CSV, and PPTX respectively) during the download. Second, the system extracts the text content from the downloaded file using the document processing pipeline. Third, the system breaks the extracted text into smaller chunks using a text splitting algorithm. Fourth, the system generates vector embeddings for each text chunk using the embedding manager. Fifth, the system stores the text chunks, embeddings, and file metadata in the database associated with the course. Sixth, and critically, the system deletes the temporary downloaded file from the server.

This entire process happens automatically for each imported file. The teacher does not need to perform any manual operations during the vectorization process. The system provides feedback on the progress, showing which file is currently being processed and the number of chunks created.

### Step 5: Searching with VTA

Once files are imported from Google Drive, the VTA can use them to answer questions. When a student or teacher asks a question to the VTA, the system searches both the in-memory vector store (for manually uploaded files) and the database (for Google Drive imported files) to find relevant content.

The search results include citations indicating which file and which page the information came from. This allows students to verify the information and access the original source if needed. The combination of manually uploaded files and Google Drive imported files in a single search index ensures that students have access to all course materials regardless of how they were imported.

---

## Technical Implementation Details

This section provides additional technical details about the implementation for reference.

### OAuth 2.0 Flow

The OAuth 2.0 flow follows the standard Google authentication protocol. The system generates an authorization URL with the following parameters: client_id, redirect_uri, response_type set to "code", the required scopes, access_type set to "offline" to receive a refresh token, prompt set to "consent" to ensure the refresh token is provided, and a state parameter for CSRF protection.

When Google redirects back to the callback URL with the authorization code, the system exchanges the code for tokens by making a POST request to Google's token endpoint. The request includes the code, client_id, client_secret, redirect_uri, and grant_type set to "authorization_code." The response includes the access_token, refresh_token, expires_in, and token_type.

When the access token expires, the system uses the refresh token to obtain a new access token without requiring user interaction. This ensures that the Google Drive connection remains active for extended periods.

### Supported File Types and Processing

The system supports several file types from Google Drive. PDF files are downloaded directly and processed using the PDF extraction pipeline. Google Docs are exported to DOCX format and then processed. Google Sheets are exported to CSV format and then processed. Google Slides are exported to PPTX format and then processed. Microsoft Word documents (.docx) are downloaded directly and processed. Plain text files (.txt) are downloaded and processed as text.

For each supported file type, the system uses the appropriate processing pipeline to extract text content. The extracted text is then chunked into overlapping segments, typically with 1000 characters per chunk and 200 characters of overlap between chunks. Each chunk is assigned an embedding using the configured embedding provider (such as Gemini or another supported provider). The chunks and their embeddings are stored in the database with references to the source file and course.

### Data Storage

The system stores the following information in the database for each imported Google Drive file. The file metadata includes the Google Drive file ID, file name, MIME type, size, the teacher's Google Drive file URL, the date and time when the file was imported, and the course ID with which the file is associated. The text chunks include the chunk text content, the chunk index within the file, the page number (if available from the source document), and the embedding vector for semantic search. The OAuth tokens include the access token (temporarily stored), the refresh token (for maintaining the connection), and the token expiration time.

The original files downloaded from Google Drive are never stored permanently. They are deleted immediately after text extraction and vectorization. This is a critical security and privacy measure that ensures the VTA system does not retain copies of the teacher's documents.

### API Endpoints

The Google Drive integration exposes several API endpoints. The /drive/auth endpoint initiates the OAuth flow by redirecting to Google. The /drive/callback endpoint handles the OAuth callback from Google. The /drive/connect endpoint stores the folder URL for a course. The /drive/files/{course_id} endpoint lists files in the connected Drive folder. The /drive/sync endpoint imports selected files and vectorizes them.

All endpoints except /drive/callback require authentication. The endpoints that modify data (/drive/connect, /drive/sync) additionally require teacher-level authorization. Students receive a 403 Forbidden error if they attempt to access these endpoints.

---

## Security Considerations

The Google Drive integration is designed with several security measures to protect teacher data and maintain the integrity of the system.

The system uses OAuth 2.0, which is the industry standard for authorizing third-party applications. Teachers grant explicit permission to the VTA application, and they can revoke this permission at any time through their Google account settings. The system requests only read-only access to Google Drive, which means it can view and download files but cannot modify, delete, or share files on the teacher's behalf.

The state parameter in the OAuth flow provides CSRF (Cross-Site Request Forgery) protection. This prevents attackers from intercepting the OAuth flow and gaining unauthorized access to the teacher's Drive.

The OAuth tokens are stored securely in the database and are not exposed to the frontend or through API responses. The system uses the refresh token pattern to maintain the connection without requiring the teacher to re-enter their credentials frequently.

The most important security measure is that the VTA system never stores the original files from Google Drive. This ensures that the teacher's documents remain under their control and that no unauthorized copies exist on the VTA system. The vectorized content (text chunks and embeddings) is stored, but this is not the same as storing the original documents.

---

## Troubleshooting Common Issues

Teachers may encounter issues when using the Google Drive integration. This section provides solutions for common problems.

If the teacher receives an error message stating "Google OAuth not configured," this means the application administrator has not set up the Google OAuth credentials. The administrator must complete the Google Cloud Console setup and add the credentials to the environment variables file. The teacher should contact their system administrator for assistance.

If the teacher receives an "invalid_client" error, the Client ID or Client Secret in the environment variables is incorrect. The teacher should verify that the credentials match exactly what was provided in the Google Cloud Console. Common issues include typos, extra spaces, or using credentials from a different project.

If the teacher receives a "redirect_uri_mismatch" error, the redirect URI configured in the Google Cloud Console does not match the redirect URI in the VTA application's environment variables. Both must match exactly, including the protocol (http vs https), the domain, and the path.

If the teacher sees an empty file list after clicking "Sync from Drive," there may be no supported files in the connected folder. The folder may be empty, or it may contain only unsupported file types (such as images or videos). The teacher should verify that their Drive folder contains supported file types.

If the import process fails for a particular file, the file may be corrupted or password-protected. The teacher should download the file directly from Google Drive to verify it opens correctly, then try re-importing. If the problem persists, the file may need to be converted to a supported format before import.

---

## Summary

The Google Drive integration feature enables teachers to connect their Google Drive to the VTA system, browse and select files from their Drive, and automatically import those files into the VTA's knowledge base. The system processes each file by extracting text, generating vector embeddings, and storing the embeddings for semantic search. Original files are not stored on the VTA system, maintaining security and data integrity. This feature streamlines the workflow for teachers by eliminating the need to manually upload files and ensuring that course materials are always accessible through the VTA.

The feature is designed with security in mind, using OAuth 2.0 for authentication, enforcing teacher-only access, and never storing original files. The integration supports multiple file types and provides a seamless user experience for importing Google Drive content into the VTA system.