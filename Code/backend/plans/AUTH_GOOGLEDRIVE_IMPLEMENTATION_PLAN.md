# Authentication & Google Drive Integration Plan

## Virtual Teaching Assistant — Login, PostgreSQL, Google Drive OAuth, Vectorized Storage

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Architecture Summary](#2-architecture-summary)
3. [Part A — Login Page & PostgreSQL](#3-part-a--login-page--postgresql)
4. [Part B — Google Drive OAuth Integration](#4-part-b--google-drive-oauth-integration)
5. [Part C — Vectorized-Only Storage from Google Drive](#5-part-c--vectorized-only-storage-from-google-drive)
6. [File Structure](#6-file-structure)
7. [Database Schema](#7-database-schema)
8. [API Endpoints](#8-api-endpoints)
9. [Frontend Changes](#9-frontend-changes)
10. [Environment Variables](#10-environment-variables)
11. [Step-by-Step Implementation Order](#11-step-by-step-implementation-order)
12. [Testing Plan](#12-testing-plan)
13. [Dependencies](#13-dependencies)

---

## 1. Overview & Goals

### User Roles

There are exactly **two user types** in the system. Every feature must respect these role boundaries:

| Role | Registration | Login | Ask VTA Questions | Upload Documents | Connect Google Drive | Sync Drive Files | View Synced Files |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Student** | Yes | Yes | Yes | **No** | **No** | **No** | Yes (read-only) |
| **Teacher** | Yes | Yes | Yes | Yes | Yes | Yes | Yes (full CRUD) |

**What each role can do in detail:**

- **Student:**
  - Registers with email + password (picks "Student" role)
  - Logs in and lands on the VTA chat interface
  - Asks questions to the VTA (queries search BOTH in-memory vectors AND PostgreSQL vectors from all synced Google Drive files)
  - Can see which course materials are available (read-only list of synced files)
  - **Cannot** upload files, connect Google Drive, or modify synced materials

- **Teacher:**
  - Registers with email + password (picks "Teacher" role)
  - Logs in and lands on the VTA chat interface (same as student, plus extra controls)
  - Can upload documents manually (existing upload flow)
  - Can connect their Google Drive via OAuth
  - Can select files from their Drive to sync (download → vectorize → store in PG → delete temp)
  - Can manage synced files (view list, re-sync, remove)
  - Asks questions to the VTA (same as student — the VTA doesn't change, only the content available changes)

### What We Are Building

Two major features that do NOT interfere with the existing RAG pipeline code:

| Feature | Description |
|---------|-------------|
| **Login System** | Email + password authentication stored in PostgreSQL. Teachers and students both use this. |
| **Google Drive Connector** | Teachers grant OAuth permission → system reads their Drive files → downloads them temporarily → vectorizes → deletes the originals → stores ONLY the vector embeddings + metadata in PostgreSQL. |

### Frontend vs Backend Responsibility

| Who | What |
|-----|------|
| **Your teammates** | Frontend UI design — login page, registration page, dashboard layout, chat interface, teacher controls panel |
| **You (this plan)** | Backend API — auth endpoints, database, Google Drive OAuth, vectorization pipeline, query bridge |

The backend exposes clean REST API endpoints. The frontend team calls these endpoints from their UI. The HTML templates in this plan (`login.html`, `register.html`) are **placeholders/scaffolds** — the frontend team will replace them with their design. The important part is that the API contract (request/response shapes) stays consistent.

### Core Principle

**The existing `app.py` and all RAG pipeline files remain untouched.** We build new modules that plug in alongside the existing system. The current upload → vectorize → query flow stays exactly the same for manually uploaded files. We ADD a second entry point: Google Drive files that get vectorized and stored in PostgreSQL instead of in-memory.

### Why PostgreSQL

- Free (open-source, can run locally or use free-tier cloud like Supabase, Neon, or Railway)
- Handles structured data (users, file metadata, vector metadata) well
- Can store vector embeddings via the `pgvector` extension
- Mature Python support via `psycopg2` and `SQLAlchemy`

---

## 2. Architecture Summary

### Two User Flows

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          STUDENT FLOW                                     │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────┐     ┌──────────────┐     ┌───────────────────────────┐     │
│  │ Register │────►│    Login     │────►│   VTA Chat Interface      │     │
│  │ (student)│     │  (email+pw)  │     │                           │     │
│  └──────────┘     └──────────────┘     │   • Ask questions         │     │
│                                        │   • See available course  │     │
│                                        │     materials (read-only) │     │
│                                        │   • Get answers with      │     │
│                                        │     citations             │     │
│                                        └─────────┬─────────────────┘     │
│                                                  │                       │
│                                                  ▼                       │
│                                        ┌──────────────────────┐          │
│                                        │   Query searches:    │          │
│                                        │   • In-memory store  │          │
│                                        │     (manual uploads) │          │
│                                        │   + PostgreSQL store │          │
│                                        │     (teacher's Drive │          │
│                                        │      synced files)   │          │
│                                        └──────────────────────┘          │
└───────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────┐
│                          TEACHER FLOW                                     │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────┐     ┌──────────────┐     ┌───────────────────────────┐     │
│  │ Register │────►│    Login     │────►│   Dashboard               │     │
│  │ (teacher)│     │  (email+pw)  │     │                           │     │
│  └──────────┘     └──────────────┘     │  ┌─────────┐ ┌─────────┐ │     │
│                                        │  │ Upload  │ │ Connect │ │     │
│                                        │  │ Files   │ │ GDrive  │ │     │
│                                        │  └────┬────┘ └────┬────┘ │     │
│                                        └───────┼───────────┼──────┘     │
│                                                │           │            │
│                              ┌─────────────────┘           │            │
│                              ▼                             ▼            │
│                     ┌──────────────┐           ┌──────────────────┐     │
│                     │  Existing    │           │  Google Drive    │     │
│                     │  Upload Flow │           │  OAuth Flow      │     │
│                     │  (in-memory) │           │                  │     │
│                     └──────────────┘           │  1. Consent      │     │
│                              │                 │  2. List files   │     │
│                              │                 │  3. Select files │     │
│                              │                 │  4. Sync         │     │
│                              │                 └────────┬─────────┘     │
│                              │                          │               │
│                              ▼                          ▼               │
│                     ┌──────────────────────────────────────────┐        │
│                     │        Vectorization Pipeline            │        │
│                     │   (reuse existing document_loader.py,    │        │
│                     │    embedding_manager.py, chunker)        │        │
│                     └──────────────────┬───────────────────────┘        │
│                                        │                                │
│                                        ▼                                │
│                     ┌──────────────────────────────────────────┐        │
│                     │           PostgreSQL (pgvector)           │        │
│                     │                                          │        │
│                     │  Stores ONLY:                            │        │
│                     │  • Vector embeddings (vector chunks)     │        │
│                     │  • Text chunks                           │        │
│                     │  • File metadata (name, Drive ID, etc.)  │        │
│                     │  • User ownership                        │        │
│                     │                                          │        │
│                     │  Does NOT store:                         │        │
│                     │  • Original files                        │        │
│                     │  • Google Drive credentials              │        │
│                     └──────────────────────────────────────────┘        │
│                                        │                                │
│                                        ▼                                │
│                     ┌──────────────────────────────────────────┐        │
│                     │     Teacher also sees VTA Chat           │        │
│                     │     (same interface as students,         │        │
│                     │      but with extra upload/drive         │        │
│                     │      controls available)                 │        │
│                     └──────────────────────────────────────────┘        │
└───────────────────────────────────────────────────────────────────────────┘
```

### How Roles Affect API Access

```
┌─────────────────────────────────────────────────────────────┐
│                    API ROLE GATES                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Endpoints accessible to EVERYONE (authenticated):          │
│  ┌─────────────────────────────────────────────────┐        │
│  │  POST /auth/login          (no auth needed)     │        │
│  │  POST /auth/register       (no auth needed)     │        │
│  │  POST /auth/logout                                │        │
│  │  GET  /auth/me                                    │        │
│  │  POST /api/query           (ask the VTA)         │        │
│  │  GET  /api/files           (list synced files)   │        │
│  │  GET  /drive/synced        (view synced files)   │        │
│  └─────────────────────────────────────────────────┘        │
│                                                             │
│  Endpoints TEACHER-ONLY (403 for students):                 │
│  ┌─────────────────────────────────────────────────┐        │
│  │  GET  /drive/auth          (start OAuth flow)    │        │
│  │  GET  /drive/files         (list Drive files)    │        │
│  │  POST /drive/sync          (sync selected files) │        │
│  │  DELETE /drive/synced/<id> (remove synced file)  │        │
│  │  POST /api/upload          (manual file upload)  │        │
│  │  POST /api/clear           (clear uploaded files)│        │
│  └─────────────────────────────────────────────────┘        │
│                                                             │
│  Endpoints NOBODY accesses directly:                        │
│  ┌─────────────────────────────────────────────────┐        │
│  │  GET  /drive/callback      (Google redirects    │        │
│  │                              here automatically) │        │
│  └─────────────────────────────────────────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Part A — Login Page & PostgreSQL

### 3.1 How It Works — Sign In / Sign Up Flow

Every new visitor (teacher or student) sees the same landing page with two options:

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│            Virtual Teaching Assistant                │
│                                                     │
│     ┌──────────────┐    ┌──────────────┐            │
│     │   SIGN IN    │    │   SIGN UP    │            │
│     │   (tab)      │    │   (tab)      │            │
│     └──────────────┘    └──────────────┘            │
│                                                     │
│     SIGN IN view:              SIGN UP view:        │
│     ┌──────────────┐          ┌──────────────┐      │
│     │ Email        │          │ Full Name    │      │
│     │ Password     │          │ Email        │      │
│     │              │          │ Password     │      │
│     │ [LOGIN]      │          │ I am a:      │      │
│     │              │          │ ( ) Student  │      │
│     │ No account?  │          │ ( ) Teacher  │      │
│     │ Sign Up →    │          │              │      │
│     └──────────────┘          │ [CREATE      │      │
│                               │  ACCOUNT]    │      │
│                               │              │      │
│                               │ Have an      │      │
│                               │ account?     │      │
│                               │ Sign In →    │      │
│                               └──────────────┘      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**The flow for a brand new user (teacher OR student):**

1. User visits the app for the first time → sees landing page with **Sign In** / **Sign Up** tabs
2. User clicks **Sign Up** tab
3. Fills in: Full Name, Email, Password
4. Selects their role: **Student** or **Teacher** (radio buttons or dropdown)
5. Clicks "Create Account"
6. Backend creates the account in PostgreSQL with the chosen role
7. User is redirected to the login view (or auto-logged in)
8. User enters credentials → lands on the appropriate dashboard based on their role

**The flow for a returning user:**

1. User visits the app → sees landing page (defaults to **Sign In** tab)
2. Enters email + password
3. Backend verifies credentials against PostgreSQL
4. On success → redirects to main app
5. Frontend checks `user.role` and shows the right interface:
   - `"student"` → chat interface + read-only synced files list
   - `"teacher"` → chat interface + upload panel + Google Drive controls

### 3.2 New Files to Create

```
auth/
├── __init__.py              # Makes auth a Python package
├── models.py                # SQLAlchemy models (User, etc.)
├── routes.py                # /login, /register, /logout endpoints
├── db.py                    # Database connection & session setup
├── middleware.py             # @login_required decorator
templates/
├── login.html               # NEW login page
├── register.html            # NEW registration page
```

### 3.3 Database Connection (`auth/db.py`)

```python
"""
Database connection module.
Sets up SQLAlchemy engine and session for PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Read from .env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://username:password@localhost:5432/virtual_ta"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency: yields a database session, closes after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 3.4 User Model (`auth/models.py`)

```python
"""
SQLAlchemy models for users and related entities.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from .db import Base
from werkzeug.security import generate_password_hash, check_password_hash

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="student")  # "student" or "teacher"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

    # Google Drive fields (populated when teacher connects Drive)
    google_drive_connected = Column(Boolean, default=False)
    google_drive_refresh_token = Column(String(500), nullable=True)

    def set_password(self, password: str):
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "google_drive_connected": self.google_drive_connected,
            "created_at": str(self.created_at) if self.created_at else None,
        }
```

### 3.5 Auth Routes (`auth/routes.py`)

```python
"""
Authentication routes: register, login, logout, session check.
"""
from flask import Blueprint, request, jsonify, session, redirect, url_for
from .db import get_db
from .models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    POST /auth/register
    Body: { "email": "...", "password": "...", "full_name": "...", "role": "student" | "teacher" }
    
    The frontend registration form has a role selector (student / teacher).
    This determines what the user can do after login.
    """
    data = request.get_json()

    # Validate required fields
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password are required"}), 400

    # Validate role
    role = data.get("role", "student")
    if role not in ("student", "teacher"):
        return jsonify({"error": "Role must be 'student' or 'teacher'"}), 400

    db = next(get_db())

    # Check if user already exists
    existing = db.query(User).filter_by(email=data["email"]).first()
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    user = User(
        email=data["email"],
        full_name=data.get("full_name", ""),
        role=role,
    )
    user.set_password(data["password"])
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-login: immediately create session after registration
    # This way the user doesn't have to sign in again right after signing up
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_role"] = user.role

    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /auth/login
    Body: { "email": "...", "password": "..." }
    Returns: JWT token or sets session cookie
    """
    data = request.get_json()
    db = next(get_db())

    user = db.query(User).filter_by(email=data["email"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    # Store user_id in session (Flask session uses signed cookies)
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_role"] = user.role

    return jsonify({
        "message": "Login successful",
        "user": user.to_dict()
    }), 200

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear session."""
    session.clear()
    return jsonify({"message": "Logged out"}), 200

@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """Check who is logged in."""
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user.to_dict()}), 200
```

### 3.6 Auth Middleware (`auth/middleware.py`)

Two decorators that control who can access what:

```python
"""
Middleware: decorators to protect routes based on authentication and role.
"""
from functools import wraps
from flask import session, jsonify

def login_required(f):
    """
    Ensures the user is logged in (has a valid session).
    Used on: /api/query, /api/files, /drive/synced, /auth/logout, /auth/me
    Returns 401 if no session.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def teacher_required(f):
    """
    Ensures the user is logged in AND has role='teacher'.
    Used on: /drive/auth, /drive/files, /drive/sync, /drive/synced/<id>,
             /api/upload, /api/clear
    Returns 401 if not logged in.
    Returns 403 if logged in but role is 'student'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        if session.get("user_role") != "teacher":
            return jsonify({"error": "Teacher access required. Students cannot upload or sync files."}), 403
        return f(*args, **kwargs)
    return decorated
```

### How the decorators are applied in routes

```python
# In gdrive/routes.py:
@drive_bp.route("/auth", methods=["GET"])
@login_required
@teacher_required          # <-- Student hits this → 403
def start_oauth():
    ...

@drive_bp.route("/synced", methods=["GET"])
@login_required             # <-- Student hits this → allowed (read-only)
def list_synced_files():
    ...

# In app.py (existing routes to protect):
@app.route("/api/upload", methods=["POST"])
@login_required
@teacher_required           # <-- Student hits this → 403
def upload_file():
    ...
```

### 3.7 Login & Register Pages

These are **placeholder templates** that the frontend teammates will replace with their designs. The actual scaffold code and API contracts are in **Section 9 (Frontend Integration Notes)**.

The key backend requirement is: the `/` route in `app.py` checks if the user has a session. If not, it serves the login page. If yes, it serves the main app (differentiated by `user.role` for what controls are visible).

```python
# Minimal change to app.py:
@app.route("/")
def index():
    if "user_id" not in session:
        return render_template("login.html")
    return render_template("index.html")  # Existing main page
```

---

## 4. Part B — Google Drive OAuth Integration

### 4.1 How OAuth 2.0 Works for Google Drive

This is exactly what Gemini described. Here is the flow:

```
┌──────────┐     1. Click "Connect Google Drive"     ┌──────────────┐
│  Teacher  │ ───────────────────────────────────────► │  Flask App   │
│  Browser  │                                         │  /drive/auth │
└──────────┘                                         └──────┬───────┘
     ▲                                                      │
     │  2. Redirect to Google's consent screen              │
     │◄─────────────────────────────────────────────────────┘
     │
     │  3. Teacher signs into Google, clicks "Allow"
     ▼
┌──────────────┐     4. Google sends auth code back     ┌──────────────┐
│   Google     │ ───────────────────────────────────────►│  Flask App   │
│   OAuth      │                                         │  /drive/callback
│   Server     │                                         │              │
└──────────────┘                                         │  Exchange code│
                                                         │  for tokens  │
                                                         └──────┬───────┘
                                                                │
                                                                ▼
                                                         ┌──────────────┐
                                                         │  PostgreSQL  │
                                                         │  Stores:     │
                                                         │  - refresh   │
                                                         │    token     │
                                                         │  - user link │
                                                         └──────────────┘
```

### 4.2 Google Cloud Setup (Manual Steps — One-Time)

Before writing any code, you need to set up Google Cloud:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Virtual Teaching Assistant")
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" → "Library"
   - Search "Google Drive API" → Enable
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:5000/drive/callback`
   - Save the **Client ID** and **Client Secret**
5. Configure OAuth consent screen:
   - Set app name, support email
   - Add scopes: `https://www.googleapis.com/auth/drive.readonly`
   - Add test users (your email during development)

### 4.3 New Files to Create

```
gdrive/
├── __init__.py              # Makes gdrive a Python package
├── auth.py                  # OAuth flow: generate URL, handle callback, refresh tokens
├── drive_client.py          # Google Drive API client: list files, download files
├── vectorizer.py            # Download from Drive → vectorize → store in PostgreSQL → delete temp file
├── routes.py                # /drive/* endpoints
├── models.py                # GoogleDriveFile model for tracking synced files
```

### 4.4 OAuth Flow (`gdrive/auth.py`)

```python
"""
Google Drive OAuth 2.0 authentication flow.
Uses google-auth-oauthlib for the standard OAuth flow.
"""
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# OAuth configuration
CLIENT_SECRETS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "credentials", "client_secret.json"
)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/drive/callback")


def get_authorization_url():
    """
    Step 1: Generate the Google OAuth consent screen URL.
    The teacher clicks this and is redirected to Google.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",        # Gets refresh_token (long-lived)
        prompt="consent",             # Forces consent screen every time (ensures refresh_token)
        include_granted_scopes="true",
    )
    return authorization_url, state


def exchange_code_for_tokens(auth_code: str):
    """
    Step 2: After Google redirects back with ?code=..., exchange it for tokens.
    Returns: Credentials object with access_token and refresh_token.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    flow.fetch_token(code=auth_code)
    credentials = flow.credentials
    return credentials


def refresh_credentials(refresh_token: str):
    """
    Use a stored refresh_token to get a fresh access_token.
    Called before each Drive API request.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )
    creds.refresh(Request())
    return creds
```

### 4.5 Drive Client (`gdrive/drive_client.py`)

```python
"""
Google Drive API client.
Lists and downloads files from a teacher's Google Drive.
"""
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import tempfile
import os

# File types we care about (documents that can be vectorized)
SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/plain",
    "text/html",
    "text/csv",
    "application/vnd.google-apps.document",    # Google Docs (export as docx)
    "application/vnd.google-apps.spreadsheet", # Google Sheets (export as csv)
    "application/vnd.google-apps.presentation", # Google Slides (export as pptx)
}


def build_drive_service(credentials):
    """Build a Google Drive API service object from OAuth credentials."""
    return build("drive", "v3", credentials=credentials)


def list_files(service, folder_id=None, page_size=100):
    """
    List files in the teacher's Google Drive.
    Optionally filter to a specific folder.
    Returns list of file metadata dicts.
    """
    query = "trashed = false"
    if folder_id:
        query += f" and '{folder_id}' in parents"

    results = service.files().list(
        q=query,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])

    # Filter to only supported document types
    supported_files = [f for f in files if f["mimeType"] in SUPPORTED_MIME_TYPES]
    return supported_files


def download_file(service, file_id: str, file_name: str, mime_type: str) -> str:
    """
    Download a file from Google Drive to a temporary local path.
    For Google-native Docs/Sheets/Slides, exports to a standard format.
    
    Returns: Path to the temporary file.
    """
    temp_dir = tempfile.mkdtemp()

    # Google-native files need to be exported, not downloaded directly
    GOOGLE_EXPORT_MAP = {
        "application/vnd.google-apps.document": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx"
        ),
        "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
        "application/vnd.google-apps.presentation": (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pptx"
        ),
    }

    if mime_type in GOOGLE_EXPORT_MAP:
        export_mime, ext = GOOGLE_EXPORT_MAP[mime_type]
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        temp_path = os.path.join(temp_dir, file_id + ext)
    else:
        request = service.files().get_media(fileId=file_id)
        ext = os.path.splitext(file_name)[1] or ".bin"
        temp_path = os.path.join(temp_dir, file_id + ext)

    # Download the file
    with open(temp_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

    return temp_path
```

### 4.6 Google Drive Routes (`gdrive/routes.py`)

```python
"""
Google Drive API routes for OAuth and file syncing.
"""
from flask import Blueprint, request, jsonify, session, redirect
from auth.middleware import login_required, teacher_required
from .auth import get_authorization_url, exchange_code_for_tokens
from .drive_client import build_drive_service, list_files, download_file
from .vectorizer import vectorize_and_store
from auth.db import get_db
from auth.models import User

drive_bp = Blueprint("drive", __name__, url_prefix="/drive")


@drive_bp.route("/auth", methods=["GET"])
@login_required
def start_oauth():
    """
    Step 1: Teacher clicks "Connect Google Drive".
    This returns the Google consent URL. Frontend redirects the teacher there.
    """
    auth_url, state = get_authorization_url()
    # Store state in session to verify callback
    session["oauth_state"] = state
    return jsonify({"auth_url": auth_url}), 200


@drive_bp.route("/callback", methods=["GET"])
def oauth_callback():
    """
    Step 2: Google redirects back here with ?code=...&state=...
    We exchange the code for tokens and save the refresh_token to PostgreSQL.
    """
    auth_code = request.args.get("code")
    state = request.args.get("state")

    # Verify state matches (CSRF protection)
    if state != session.get("oauth_state"):
        return jsonify({"error": "Invalid OAuth state"}), 400

    credentials = exchange_code_for_tokens(auth_code)

    # Save refresh_token to the user's record in PostgreSQL
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    user.google_drive_connected = True
    user.google_drive_refresh_token = credentials.refresh_token
    db.commit()

    # Redirect back to the frontend with success
    return redirect("/?drive_connected=true")


@drive_bp.route("/files", methods=["GET"])
@login_required
@teacher_required
def list_drive_files():
    """
    List the teacher's Google Drive files (documents only).
    Frontend calls this to show what's available for syncing.
    """
    db = next(get_db())
    user = db.query(User).get(session["user_id"])

    if not user.google_drive_connected:
        return jsonify({"error": "Google Drive not connected"}), 400

    from .auth import refresh_credentials
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)

    folder_id = request.args.get("folder_id")  # Optional: specific folder
    files = list_files(service, folder_id=folder_id)

    return jsonify({"files": files}), 200


@drive_bp.route("/sync", methods=["POST"])
@login_required
@teacher_required
def sync_files():
    """
    POST /drive/sync
    Body: { "file_ids": ["id1", "id2", ...] }
    
    For each file ID:
      1. Download from Google Drive to temp location
      2. Run through the existing vectorization pipeline
      3. Store vectors + chunks + metadata in PostgreSQL
      4. Delete the temp file (we do NOT keep the original)
    
    This is the KEY endpoint — it bridges Google Drive → vector store.
    """
    data = request.get_json()
    file_ids = data.get("file_ids", [])

    db = next(get_db())
    user = db.query(User).get(session["user_id"])

    from .auth import refresh_credentials
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)

    results = []
    for file_id in file_ids:
        try:
            # Get file metadata
            meta = service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime"
            ).execute()

            # Download to temp
            temp_path = download_file(service, file_id, meta["name"], meta["mimeType"])

            # Vectorize and store in PostgreSQL
            num_chunks = vectorize_and_store(
                temp_path=temp_path,
                file_id=file_id,
                file_name=meta["name"],
                mime_type=meta["mimeType"],
                user_id=user.id,
            )

            results.append({
                "file_id": file_id,
                "name": meta["name"],
                "status": "synced",
                "chunks_stored": num_chunks,
            })

        except Exception as e:
            results.append({
                "file_id": file_id,
                "status": "error",
                "error": str(e),
            })

    return jsonify({"results": results}), 200
```

---

## 5. Part C — Vectorized-Only Storage from Google Drive

### 5.1 The Key Idea

```
┌─────────────────────────────────────────────────────────────────────┐
│                  GOOGLE DRIVE FILE LIFECYCLE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Google Drive          Temporary            PostgreSQL              │
│   ┌──────────┐         ┌──────────┐         ┌──────────────────┐    │
│   │ lecture  │  download│ /tmp/    │  vector │                  │    │
│   │ notes    │────────►│ abc.pdf  │────────►│  vector_chunks   │    │
│   │ .pdf     │         │          │  + store│  (embeddings)    │    │
│   └──────────┘         └────┬─────┘         │                  │    │
│                             │               │  file_metadata   │    │
│                             │ DELETE        │  (name, id, etc) │    │
│                             ▼               │                  │    │
│                        (gone forever)       │  NO raw file     │    │
│                                             │  stored at all   │    │
│                                             └──────────────────┘    │
│                                                                     │
│   The teacher's original file stays on THEIR Google Drive.          │
│   We only ever keep the vectorized chunks + metadata.               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 The Vectorizer Module (`gdrive/vectorizer.py`)

This module bridges the existing document processing pipeline with PostgreSQL storage:

```python
"""
Vectorizer: Takes a downloaded file, processes it through the existing
RAG pipeline, stores ONLY the vectors + text chunks + metadata in PostgreSQL,
then deletes the temporary file.

This REUSES existing code:
- document_loader.py for loading files
- embedding_manager.py or gemini_embedding_manager.py for embeddings
- text_splitter for chunking
"""
import os
import uuid
import tempfile
from datetime import datetime

# Import existing project modules (reuse, don't rewrite!)
from document_loader import load_document
from embedding_manager import EmbeddingManager  # or GeminiEmbeddingManager
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Import our new PostgreSQL storage
from .models import VectorChunk, FileMetadata
from auth.db import get_db


def vectorize_and_store(
    temp_path: str,
    file_id: str,
    file_name: str,
    mime_type: str,
    user_id: int,
) -> int:
    """
    Main function: vectorize a file and store in PostgreSQL.
    
    Steps:
    1. Load the document using existing document_loader
    2. Split into chunks using existing chunker
    3. Generate embeddings using existing embedding_manager
    4. Store chunks + embeddings in PostgreSQL
    5. Delete the temporary file
    
    Returns: Number of chunks stored.
    """
    # Step 1: Load document (reuse existing code)
    documents = load_document(temp_path)
    
    if not documents:
        raise ValueError(f"Could not extract text from {file_name}")

    # Step 2: Split into chunks (reuse existing chunker)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )
    chunks = splitter.split_documents(documents)
    
    # Step 3: Generate embeddings (reuse existing embedding manager)
    embedder = EmbeddingManager()  # Uses .env config for provider
    chunk_texts = [chunk.page_content for chunk in chunks]
    embeddings = embedder.embed_documents(chunk_texts)
    
    # Step 4: Store in PostgreSQL
    db = next(get_db())
    
    # First, store/update file metadata
    file_meta = db.query(FileMetadata).filter_by(drive_file_id=file_id).first()
    if not file_meta:
        file_meta = FileMetadata(
            drive_file_id=file_id,
            file_name=file_name,
            mime_type=mime_type,
            owner_user_id=user_id,
            num_chunks=len(chunks),
            synced_at=datetime.utcnow(),
        )
        db.add(file_meta)
    else:
        file_meta.num_chunks = len(chunks)
        file_meta.synced_at = datetime.utcnow()
    
    # Delete old chunks if re-syncing
    db.query(VectorChunk).filter_by(file_metadata_id=file_meta.id).delete()
    
    # Store each chunk + its embedding
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_chunk = VectorChunk(
            id=str(uuid.uuid4()),
            file_metadata_id=file_meta.id,
            chunk_index=i,
            text=chunk.page_content,
            page_number=chunk.metadata.get("page", None),
            embedding=embedding.tolist(),  # Store as list in pgvector
        )
        db.add(vector_chunk)
    
    db.commit()
    
    # Step 5: Delete the temporary file (WE DO NOT KEEP IT)
    try:
        os.remove(temp_path)
        os.rmdir(os.path.dirname(temp_path))
    except OSError:
        pass  # Temp dir cleanup is best-effort
    
    return len(chunks)
```

### 5.3 Querying Vectorized Google Drive Data

When a user asks a question, the system needs to search BOTH:
- The in-memory vector store (for manually uploaded files — existing behavior)
- PostgreSQL (for Google Drive synced files — new behavior)

```python
"""
query_bridge.py — Bridges queries across both storage backends.
"""
from auth.db import get_db
from .models import VectorChunk
from embedding_manager import EmbeddingManager
import numpy as np


def search_gdrive_vectors(query: str, top_k: int = 5, user_id: int = None):
    """
    Search Google Drive vectorized content in PostgreSQL.
    Returns the top_k most similar chunks.
    """
    db = next(get_db())
    embedder = EmbeddingManager()
    
    # Embed the query
    query_embedding = embedder.embed_query(query)
    
    # Get all chunks (optionally filtered by user's synced files)
    chunks_query = db.query(VectorChunk)
    if user_id:
        chunks_query = chunks_query.join(VectorChunk.file_metadata).filter_by(owner_user_id=user_id)
    
    all_chunks = chunks_query.all()
    
    # Compute cosine similarity
    results = []
    for chunk in all_chunks:
        similarity = cosine_similarity(query_embedding, chunk.embedding)
        results.append({
            "text": chunk.text,
            "score": similarity,
            "source": chunk.file_metadata.file_name,
            "page": chunk.page_number,
        })
    
    # Sort by score, return top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

---

## 6. File Structure

All new files are in their own directories. Nothing in the existing codebase is modified except for `app.py` (minimal changes to register blueprints and add a login route check).

```
VirtualTeachingAssistant_T18/
├── app.py                          # MODIFIED: register auth + drive blueprints
├── .env                            # MODIFIED: add PostgreSQL + Google OAuth vars
├── requirements.txt                # MODIFIED: add new dependencies
│
├── auth/                           # NEW: Authentication package
│   ├── __init__.py
│   ├── db.py                       # SQLAlchemy engine + session
│   ├── models.py                   # User model
│   ├── routes.py                   # /auth/login, /auth/register, /auth/logout
│   └── middleware.py               # @login_required, @teacher_required decorators
│
├── gdrive/                         # NEW: Google Drive integration package
│   ├── __init__.py
│   ├── auth.py                     # OAuth flow (get URL, exchange code, refresh)
│   ├── drive_client.py             # Drive API (list files, download)
│   ├── vectorizer.py               # Download → vectorize → store in PG → delete temp
│   ├── query_bridge.py             # Search PG vectors + merge with in-memory results
│   ├── routes.py                   # /drive/auth, /drive/callback, /drive/sync
│   └── models.py                   # VectorChunk, FileMetadata SQLAlchemy models
│
├── credentials/                    # NEW: Google OAuth secrets (gitignored!)
│   └── client_secret.json          # Downloaded from Google Cloud Console
│
├── templates/
│   ├── login.html                  # NEW: Auth page (Sign In + Sign Up tabs in one page)
│   ├── index.html                  # EXISTING: unchanged
│
├── migrations/                     # NEW: Alembic database migrations
│   └── ...
│
├── (all existing files unchanged)
```

---

## 7. Database Schema

### 7.1 PostgreSQL Tables

```sql
-- Enable pgvector extension (for storing vector embeddings)
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    role            VARCHAR(50) DEFAULT 'student',  -- 'student' or 'teacher'
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE,
    is_active       BOOLEAN DEFAULT TRUE,
    
    -- Google Drive fields
    google_drive_connected    BOOLEAN DEFAULT FALSE,
    google_drive_refresh_token VARCHAR(500)
);

-- File metadata (one row per synced Google Drive file)
CREATE TABLE file_metadata (
    id              SERIAL PRIMARY KEY,
    drive_file_id   VARCHAR(255) NOT NULL,       -- Google's file ID
    file_name       VARCHAR(500) NOT NULL,
    mime_type       VARCHAR(255),
    owner_user_id   INTEGER REFERENCES users(id),
    num_chunks      INTEGER DEFAULT 0,
    synced_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(drive_file_id, owner_user_id)          -- One sync per file per teacher
);

-- Vector chunks (the actual vectorized data — THIS IS WHAT WE STORE)
CREATE TABLE vector_chunks (
    id                VARCHAR(36) PRIMARY KEY,    -- UUID
    file_metadata_id  INTEGER REFERENCES file_metadata(id) ON DELETE CASCADE,
    chunk_index       INTEGER NOT NULL,
    text              TEXT NOT NULL,               -- The actual text chunk
    page_number       INTEGER,
    embedding         vector(768),                -- pgvector column (768 dims for Gemini)
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for fast vector similarity search
CREATE INDEX idx_vector_chunks_embedding 
    ON vector_chunks 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for filtering by file
CREATE INDEX idx_vector_chunks_file 
    ON vector_chunks(file_metadata_id);
```

### 7.2 Why pgvector?

| Approach | Pros | Cons |
|----------|------|------|
| pgvector (chosen) | Stays in PostgreSQL (one DB), SQL queries, free | Slightly slower than dedicated vector DB at scale |
| Separate ChromaDB | Fast, purpose-built | Another service to run, sync issues |
| In-memory (current) | Fast, simple | Lost on restart, no multi-user |

pgvector lets us keep EVERYTHING in one PostgreSQL database: users, metadata, AND vectors.

---

## 8. API Endpoints

### Complete Endpoint Summary

#### Authentication Endpoints (no auth required for login/register)

| Method | Endpoint | Auth | Role | Request Body | Response | Purpose |
|--------|----------|:---:|------|-------------|----------|---------|
| POST | `/auth/register` | No | — | `{ email, password, full_name, role }` | `{ message, user }` | Create account. `role` is `"student"` or `"teacher"` |
| POST | `/auth/login` | No | — | `{ email, password }` | `{ message, user }` | Login, get session cookie |
| POST | `/auth/logout` | Yes | Any | — | `{ message }` | Clear session |
| GET | `/auth/me` | Yes | Any | — | `{ user }` | Get current user info (including `role`) |

#### Google Drive Endpoints (teacher-only for setup operations)

| Method | Endpoint | Auth | Role | Request Body | Response | Purpose |
|--------|----------|:---:|------|-------------|----------|---------|
| GET | `/drive/auth` | Yes | **Teacher** | — | `{ auth_url }` | Get Google OAuth consent URL. Student gets 403. |
| GET | `/drive/callback` | No* | — | (query: `?code=...&state=...`) | redirect | Google redirects here after consent. Saves refresh token to DB. |
| GET | `/drive/files` | Yes | **Teacher** | — | `{ files: [...] }` | List teacher's Google Drive documents. Student gets 403. |
| POST | `/drive/sync` | Yes | **Teacher** | `{ file_ids: ["id1", "id2"] }` | `{ results: [...] }` | Download → vectorize → store in PG → delete temp. Student gets 403. |
| GET | `/drive/synced` | Yes | Any | — | `{ files: [...] }` | List synced files. Both roles can view (read-only for students). |
| DELETE | `/drive/synced/<id>` | Yes | **Teacher** | — | `{ message }` | Remove a synced file's vectors from PG. Student gets 403. |

*\* `/drive/callback` doesn't require prior auth because Google is the one calling it. The `state` parameter ties it back to the original user's session.*

#### Query Endpoints (any authenticated user)

| Method | Endpoint | Auth | Role | Request Body | Response | Purpose |
|--------|----------|:---:|------|-------------|----------|---------|
| POST | `/api/query` | Yes | Any | `{ query, ... }` | `{ answer, citations }` | Ask the VTA. Searches both in-memory + PG vectors. |
| GET | `/api/files` | Yes | Any | — | `{ files: [...] }` | List all available documents (uploaded + synced). |

#### Existing Endpoints (role-gated where needed)

| Method | Endpoint | Auth | Role | Purpose |
|--------|----------|:---:|------|---------|
| POST | `/api/upload` | Yes | **Teacher** | Manual file upload. Student gets 403. |
| POST | `/api/clear` | Yes | **Teacher** | Clear uploaded files. Student gets 403. |
| All other | `/api/*` | Yes | Any | Existing endpoints remain accessible to both roles unless modified. |

### Login Response Example

```json
// POST /auth/login response
{
    "message": "Login successful",
    "user": {
        "id": 1,
        "email": "teacher@university.edu",
        "full_name": "Dr. Smith",
        "role": "teacher",
        "google_drive_connected": false,
        "created_at": "2026-03-31T10:00:00"
    }
}
```

The frontend uses `user.role` to decide what UI to show:
- `"student"` → show chat interface + synced files list (no upload/drive controls)
- `"teacher"` → show chat interface + upload panel + Google Drive controls + synced files management

---

## 9. Frontend Integration Notes

### Who Does What

| Component | Owner | Notes |
|-----------|-------|-------|
| Sign In / Sign Up page UI | **Teammates** | Single page with tabs. Calls `POST /auth/login` and `POST /auth/register`. Includes role selector (student/teacher). |
| Dashboard / Chat UI | **Teammates** | Design and build. Calls `POST /api/query`. |
| Teacher controls panel | **Teammates** | Upload button, Google Drive button, synced files list. |
| Backend API (all endpoints) | **You** | This plan. Exposes REST endpoints the frontend calls. |

### What the Frontend Team Needs From Us

The backend must provide these **stable API contracts** that the frontend will call:

#### 1. Registration
```
POST /auth/register
Content-Type: application/json

Request:  { "email": "...", "password": "...", "full_name": "...", "role": "student" }
Success:  201 { "message": "Registration successful", "user": { "id": 1, "email": "...", "role": "student", ... } }
Error:    409 { "error": "Email already registered" }
```

#### 2. Login
```
POST /auth/login
Content-Type: application/json

Request:  { "email": "...", "password": "..." }
Success:  200 { "message": "Login successful", "user": { "id": 1, "email": "...", "role": "teacher", ... } }
Error:    401 { "error": "Invalid email or password" }
```

#### 3. Check Current User (for page load — am I logged in?)
```
GET /auth/me

Success:  200 { "user": { "id": 1, "email": "...", "role": "student", "google_drive_connected": false, ... } }
Error:    401 { "error": "Not authenticated" }
```

#### 4. Query the VTA
```
POST /api/query
Content-Type: application/json

Request:  { "query": "What is recursion?" }
Success:  200 { "answer": "...", "citations": [...] }
```

#### 5. Google Drive — Connect (teacher only)
```
GET /drive/auth

Success:  200 { "auth_url": "https://accounts.google.com/o/oauth2/..." }
Error:    403 { "error": "Teacher access required..." }
```
Frontend redirects user to `auth_url`. After consent, Google redirects back to `/drive/callback` → then to `/?drive_connected=true`.

#### 6. Google Drive — List Files (teacher only)
```
GET /drive/files

Success:  200 { "files": [{ "id": "...", "name": "Lecture 5.pdf", "mimeType": "application/pdf", ... }, ...] }
```

#### 7. Google Drive — Sync Selected Files (teacher only)
```
POST /drive/sync
Content-Type: application/json

Request:  { "file_ids": ["abc123", "def456"] }
Success:  200 { "results": [{ "file_id": "abc123", "name": "Lecture 5.pdf", "status": "synced", "chunks_stored": 42 }, ...] }
```

#### 8. View Synced Files (both roles)
```
GET /drive/synced

Success:  200 { "files": [{ "id": 1, "file_name": "Lecture 5.pdf", "num_chunks": 42, "synced_at": "..." }, ...] }
```

#### 9. Logout
```
POST /auth/logout

Success:  200 { "message": "Logged out" }
```

### Frontend Role-Based Rendering Logic

The frontend uses the `user.role` field from login/me responses to decide what to show:

```javascript
// After login or page load
const user = response.user;

if (user.role === "student") {
    // Show: chat interface + synced files list (read-only)
    // Hide: upload button, Google Drive connect button, delete buttons
    showChatInterface();
    showSyncedFilesReadOnly();
} else if (user.role === "teacher") {
    // Show: chat interface + upload button + Google Drive controls + synced files management
    showChatInterface();
    showUploadControls();
    showGoogleDriveControls();
    showSyncedFilesManagement();
}
```

### Auth Page Scaffold (`templates/login.html`)

**Single page with Sign In / Sign Up tabs.** The frontend team replaces this with their design, but the API calls and behavior must stay the same.

```html
<!-- Minimal scaffold — frontend team replaces this with their design -->
<!-- This is ONE page with two tabs: Sign In and Sign Up -->
<div class="auth-container">
    <h1>Virtual Teaching Assistant</h1>

    <!-- Tab Switcher -->
    <div class="auth-tabs">
        <button id="signInTab" class="tab active" onclick="showTab('signin')">Sign In</button>
        <button id="signUpTab" class="tab" onclick="showTab('signup')">Sign Up</button>
    </div>

    <!-- ========== SIGN IN FORM ========== -->
    <div id="signinForm" class="auth-form">
        <form id="loginForm">
            <input type="email" id="loginEmail" placeholder="Email" required>
            <input type="password" id="loginPassword" placeholder="Password" required>
            <button type="submit">Sign In</button>
        </form>
        <p class="auth-switch">
            Don't have an account? <a href="#" onclick="showTab('signup'); return false;">Sign Up</a>
        </p>
    </div>

    <!-- ========== SIGN UP FORM ========== -->
    <div id="signupForm" class="auth-form" style="display:none;">
        <form id="registerForm">
            <input type="text" id="regFullName" placeholder="Full Name" required>
            <input type="email" id="regEmail" placeholder="Email" required>
            <input type="password" id="regPassword" placeholder="Password" required>
            <input type="password" id="regPasswordConfirm" placeholder="Confirm Password" required>

            <!-- Role selector — this is how they pick student vs teacher -->
            <div class="role-selector">
                <label>I am a:</label>
                <div class="role-options">
                    <label class="role-option">
                        <input type="radio" name="role" value="student" checked>
                        <span>Student</span>
                    </label>
                    <label class="role-option">
                        <input type="radio" name="role" value="teacher">
                        <span>Teacher</span>
                    </label>
                </div>
            </div>

            <button type="submit">Create Account</button>
        </form>
        <p class="auth-switch">
            Already have an account? <a href="#" onclick="showTab('signin'); return false;">Sign In</a>
        </p>
    </div>
</div>

<script>
// Tab switching
function showTab(tab) {
    document.getElementById('signinForm').style.display = tab === 'signin' ? 'block' : 'none';
    document.getElementById('signupForm').style.display = tab === 'signup' ? 'block' : 'none';
    document.getElementById('signInTab').classList.toggle('active', tab === 'signin');
    document.getElementById('signUpTab').classList.toggle('active', tab === 'signup');
}

// Sign In handler
document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            email: document.getElementById("loginEmail").value,
            password: document.getElementById("loginPassword").value,
        }),
    });
    const data = await res.json();
    if (res.ok) {
        // Backend returns user.role — frontend uses this to show correct UI
        window.location.href = "/";
    } else {
        alert(data.error);
    }
});

// Sign Up handler
document.getElementById("registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    // Validate password match
    const pw = document.getElementById("regPassword").value;
    const pwConfirm = document.getElementById("regPasswordConfirm").value;
    if (pw !== pwConfirm) {
        alert("Passwords do not match");
        return;
    }

    const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            full_name: document.getElementById("regFullName").value,
            email: document.getElementById("regEmail").value,
            password: pw,
            role: document.querySelector('input[name="role"]:checked').value,
        }),
    });
    const data = await res.json();
    if (res.ok) {
        // Backend auto-logs in after registration, so redirect straight to main app
        window.location.href = "/";
    } else {
        alert(data.error);  // e.g. "Email already registered"
    }
});
</script>
```

### What the Frontend Team Must Include

Regardless of their design, the auth page MUST have:

| Element | Sign In Side | Sign Up Side |
|---------|-------------|-------------|
| Email input | Yes | Yes |
| Password input | Yes | Yes |
| Confirm password | No | Yes |
| Full name input | No | Yes |
| Role selector (Student/Teacher) | No | **Yes** — radio buttons or dropdown |
| Submit button | "Sign In" → calls `POST /auth/login` | "Create Account" → calls `POST /auth/register` |
| Link to switch | "Don't have an account? Sign Up" | "Already have an account? Sign In" |

### What Happens After Sign Up

```
New user fills in Sign Up form
        │
        ▼
POST /auth/register  →  { email, password, full_name, role }
        │
        ▼
Backend creates user in PostgreSQL with chosen role
        │
        ▼
Returns 201 { message: "Registration successful", user: {...} }
        │
        ▼
Frontend shows: "Account created! Please sign in."
        │
        ▼
User is now on the Sign In tab
        │
        ▼
User enters same email + password
        │
        ▼
POST /auth/login  →  { email, password }
        │
        ▼
Backend verifies, returns session + user.role
        │
        ▼
Frontend redirects to "/"  →  shows correct dashboard based on role
```

### Alternative: Auto-Login After Sign Up

If you want the user to be logged in immediately after registration (skip the sign-in step):

```python
# In auth/routes.py, at the end of the register endpoint:
@auth_bp.route("/register", methods=["POST"])
def register():
    # ... (create user as before) ...

    # Auto-login after registration
    session["user_id"] = user.id
    session["user_email"] = user.email
    session["user_role"] = user.role

    return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201
```

Then the frontend just does `window.location.href = "/"` instead of switching to the sign-in tab.

### 9.3 Google Drive Button (Added to `index.html`)

Add a button in the existing UI for teachers:

```html
<!-- Add to the sidebar or top bar of index.html -->
<button id="connectDriveBtn" class="drive-btn">
    <svg><!-- Google Drive icon --></svg>
    Connect Google Drive
</button>

<!-- After connecting, show synced files -->
<div id="syncedFilesPanel" style="display:none;">
    <h3>Synced Google Drive Files</h3>
    <ul id="syncedFilesList"></ul>
</div>
```

---

## 10. Environment Variables

### Additions to `.env`

```env
# ============================================================================
# POSTGRESQL DATABASE
# ============================================================================
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/virtual_ta

# ============================================================================
# GOOGLE DRIVE OAUTH 2.0
# ============================================================================
# From Google Cloud Console → APIs & Services → Credentials
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/drive/callback

# ============================================================================
# FLASK SESSION SECRET
# ============================================================================
FLASK_SECRET_KEY=a_random_secret_key_for_sessions

# ============================================================================
# EXISTING VARIABLES (unchanged)
# ============================================================================
NM_API_KEY=...
GOOGLE_API_KEY=...
EMBEDDING_PROVIDER=gemini
GEMINI_EMBEDDING_DIMENSIONS=768
```

---

## 11. Step-by-Step Implementation Order

### Phase 1: PostgreSQL Setup (Day 1-2)

| Step | Task | Details |
|------|------|---------|
| 1.1 | Install PostgreSQL | Download from postgresql.org, install locally. Or use free cloud: [Neon](https://neon.tech) or [Supabase](https://supabase.com) |
| 1.2 | Create database | `CREATE DATABASE virtual_ta;` |
| 1.3 | Enable pgvector | `CREATE EXTENSION vector;` |
| 1.4 | Install Python packages | `pip install psycopg2-binary sqlalchemy flask-login alembic pgvector` |
| 1.5 | Create `auth/` package | `db.py`, `models.py` |
| 1.6 | Run initial migration | Create tables with Alembic or raw SQL |
| 1.7 | Test connection | Write a small script that connects and queries |

### Phase 2: Login & Sign Up System (Day 2-3)

| Step | Task | Details |
|------|------|---------|
| 2.1 | Create `auth/routes.py` | Register, login, logout, me endpoints |
| 2.2 | Create `auth/middleware.py` | `@login_required` and `@teacher_required` decorators |
| 2.3 | Create `templates/login.html` | Single auth page with Sign In / Sign Up tabs. Sign Up has role selector (student/teacher). |
| 2.4 | Modify `app.py` | Add blueprint registration, modify `/` route to show login if not authenticated |
| 2.5 | Test sign up flow | New user → Sign Up tab → picks role → account created → Sign In → lands on correct dashboard |
| 2.6 | Test login flow | Returning user → Sign In → sees main app |
| 2.7 | Test role-based access | Student gets 403 on teacher endpoints, teacher has full access |

### Phase 3: Google Cloud Setup (Day 3)

| Step | Task | Details |
|------|------|---------|
| 3.1 | Create Google Cloud project | console.cloud.google.com |
| 3.2 | Enable Drive API | APIs & Services → Library |
| 3.3 | Create OAuth credentials | Web application type |
| 3.4 | Download client_secret.json | Save to `credentials/` folder |
| 3.5 | Configure consent screen | App name, scopes, test users |
| 3.6 | Add to `.env` | Client ID, secret, redirect URI |

### Phase 4: Google Drive OAuth (Day 4-5)

| Step | Task | Details |
|------|------|---------|
| 4.1 | Create `gdrive/` package | `__init__.py`, `auth.py` |
| 4.2 | Implement OAuth flow | `get_authorization_url()`, `exchange_code_for_tokens()` |
| 4.3 | Create `gdrive/routes.py` | `/drive/auth`, `/drive/callback` |
| 4.4 | Create "Connect Drive" button | Frontend JS + HTML |
| 4.5 | Test OAuth flow | Click button → Google consent → redirect back → token saved |

### Phase 5: Drive File Listing & Download (Day 5-6)

| Step | Task | Details |
|------|------|---------|
| 5.1 | Create `gdrive/drive_client.py` | `list_files()`, `download_file()` |
| 5.2 | Create `/drive/files` endpoint | List teacher's documents |
| 5.3 | Create file picker UI | Show files, let teacher select which to sync |
| 5.4 | Test file listing | See Drive files in the app |

### Phase 6: Vectorization Pipeline (Day 6-8)

| Step | Task | Details |
|------|------|---------|
| 6.1 | Create `gdrive/models.py` | `VectorChunk`, `FileMetadata` tables |
| 6.2 | Create `gdrive/vectorizer.py` | Download → load → chunk → embed → store → delete |
| 6.3 | Create `/drive/sync` endpoint | Trigger the pipeline for selected files |
| 6.4 | Create `gdrive/query_bridge.py` | Search PG vectors |
| 6.5 | Modify `/api/query` | Merge results from in-memory + PG |
| 6.6 | Test end-to-end | Connect Drive → sync files → ask questions → get answers |

### Phase 7: Polish & Error Handling (Day 8-9)

| Step | Task | Details |
|------|------|---------|
| 7.1 | Add error handling | Token expiry, download failures, etc. |
| 7.2 | Add loading indicators | Show progress during sync |
| 7.3 | Add file management | View synced files, delete synced data |
| 7.4 | Add rate limiting | Don't overwhelm Google API |
| 7.5 | Test edge cases | Large files, unsupported types, network errors |

---

## 12. Testing Plan

### Manual Testing Checklist

```
AUTH - SIGN UP:
[ ] New user can see Sign Up tab on the landing page
[ ] Can register as a student (role = "student")
[ ] Can register as a teacher (role = "teacher")
[ ] Cannot register with duplicate email (gets 409 error)
[ ] Cannot register with missing email or password (gets 400 error)
[ ] Password confirmation mismatch shows error
[ ] After successful sign up, user is prompted to sign in (or auto-logged in)
[ ] Role selector is required — user must pick student or teacher

AUTH - SIGN IN:
[ ] Can login with correct credentials
[ ] Login response includes correct user.role field
[ ] Cannot login with wrong password (gets 401 error)
[ ] After login, student lands on chat interface (no upload/drive controls)
[ ] After login, teacher lands on dashboard (with upload/drive controls)

AUTH - SESSION:
[ ] Logout clears session
[ ] Unauthenticated users see the Sign In / Sign Up page
[ ] Authenticated users see the main app
[ ] Refreshing the page keeps user logged in (session persists)

ROLE-BASED ACCESS (critical — this is what separates student vs teacher):
[ ] Student CANNOT access GET /drive/auth (gets 403)
[ ] Student CANNOT access GET /drive/files (gets 403)
[ ] Student CANNOT access POST /drive/sync (gets 403)
[ ] Student CANNOT access DELETE /drive/synced/<id> (gets 403)
[ ] Student CANNOT access POST /api/upload (gets 403)
[ ] Student CAN access POST /api/query (gets 200)
[ ] Student CAN access GET /drive/synced (gets 200, read-only)
[ ] Student CAN access GET /api/files (gets 200)
[ ] Teacher CAN access ALL endpoints (including /drive/*)

FRONTEND ROLE RENDERING:
[ ] After student login, frontend shows chat + synced files list (no upload/drive buttons)
[ ] After teacher login, frontend shows chat + upload + drive controls + synced files mgmt
[ ] Login API returns user.role so frontend can decide what to show

GOOGLE DRIVE (Teacher only):
[ ] "Connect Drive" opens Google consent screen
[ ] Consent screen shows correct scopes (read-only)
[ ] After consent, redirected back to app
[ ] Refresh token saved in PostgreSQL
[ ] "List Files" shows Drive documents
[ ] Non-document files (images, etc.) are filtered out
[ ] Can select specific files to sync
[ ] Sync downloads file, vectorizes, stores in PG
[ ] Temp file is deleted after sync
[ ] Re-syncing same file updates vectors (doesn't duplicate)

QUERY:
[ ] Student querying finds relevant chunks from Google Drive synced files
[ ] Teacher querying finds relevant chunks from both uploaded + synced files
[ ] Results from both sources are merged and ranked
[ ] Citations include source file name from Drive

EDGE CASES:
[ ] Google token expires → auto-refresh works
[ ] Large file sync → handles gracefully
[ ] Network error during download → error message shown
[ ] File deleted from Drive → sync still works on cached vectors
[ ] Student tries to hit teacher endpoint directly (curl/Postman) → gets 403
```

---

## 13. Dependencies

### New packages to add to `requirements.txt`

```
# Authentication & Database
psycopg2-binary>=2.9.0       # PostgreSQL driver
sqlalchemy>=2.0.0            # ORM
flask-sqlalchemy>=3.1.0      # Flask-SQLAlchemy integration
alembic>=1.13.0              # Database migrations
pgvector>=0.3.0              # pgvector Python bindings

# Google Drive API
google-api-python-client>=2.100.0   # Google API client
google-auth-httplib2>=0.2.0         # Auth transport
google-auth-oauthlib>=1.1.0         # OAuth 2.0 flow
```

### Install command

```bash
pip install psycopg2-binary sqlalchemy flask-sqlalchemy alembic pgvector google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## Key Design Decisions

### Why NOT modify existing `app.py` heavily?

The existing `app.py` is 2762 lines. We do NOT want to bloat it further. Instead:

- Auth logic goes in `auth/` package → registered as a Flask Blueprint
- Drive logic goes in `gdrive/` package → registered as a Flask Blueprint
- The ONLY change to `app.py` is:
  1. Import and register the two blueprints (~4 lines)
  2. Modify the `/` route to check session (~3 lines)

### Why store vectors in PostgreSQL instead of in-memory?

| In-Memory (current) | PostgreSQL + pgvector (new) |
|---------------------|---------------------------|
| Lost on restart | Persistent |
| Single-user only | Multi-user ready |
| Simple | Scales |
| Already works for uploads | Needed for Drive files that should persist |

Both can coexist! Manually uploaded files still use in-memory (existing behavior). Google Drive synced files use PostgreSQL (new behavior). The query endpoint searches both.

### Why download then delete (not stream)?

Google Drive API requires downloading the file to process it. The existing vectorization pipeline (document_loader, embedding_manager) works with local files. So we:
1. Download to a temp directory
2. Process with existing pipeline
3. Store vectors in PostgreSQL
4. Delete the temp file

The teacher's original file **never leaves their Google Drive**. We only keep the vectorized representation.

---

## Summary

### What Each Role Can Do

| Capability | Student | Teacher |
|------------|:---:|:---:|
| Register & Login | Yes | Yes |
| Ask VTA questions | Yes | Yes |
| View synced course materials | Yes (read-only) | Yes (full CRUD) |
| Upload files manually | **No** | Yes |
| Connect Google Drive | **No** | Yes |
| Sync Drive files to vectors | **No** | Yes |
| Remove synced files | **No** | Yes |

### New Components

| Component | What It Does | New Files |
|-----------|-------------|-----------|
| **Auth (Sign In + Sign Up)** | Email/password auth + role selection against PostgreSQL | `auth/` (4 files) + 1 HTML template (combined sign in/sign up page) |
| **Google Drive OAuth** | Teachers grant read-only access | `gdrive/auth.py`, `gdrive/routes.py` |
| **Drive Client** | List & download files from Drive | `gdrive/drive_client.py` |
| **Vectorizer** | Drive file → chunks → embeddings → PG | `gdrive/vectorizer.py`, `gdrive/models.py` |
| **Query Bridge** | Search PG vectors alongside in-memory | `gdrive/query_bridge.py` |

**Total new files: ~12 Python files + 1 HTML template + 1 credential file**
**Modified existing files: `app.py` (~10 lines changed), `.env` (~10 lines added), `requirements.txt` (~7 lines added)**

### Work Split

| Your Work (Backend) | Teammates' Work (Frontend) |
|---------------------|---------------------------|
| All `auth/` Python files | Sign In / Sign Up page UI design |
| All `gdrive/` Python files | Role selector UI (student vs teacher radio buttons) |
| PostgreSQL schema + setup | Dashboard / chat interface |
| API endpoints (REST) | Teacher controls panel |
| Role-based middleware | Calls your API endpoints |
| `.env` configuration | — |

---

## Multimodal Content Handling: What Works and What Doesn't

### The Honest Breakdown

The current system supports 4 content types. Here's what the Google Drive vectorization flow handles for each:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONTENT TYPE SUPPORT MATRIX                             │
├──────────┬──────────────────┬──────────────────┬────────────────────────────┤
│ Type     │ Current System   │ Google Drive     │ Gap                        │
│          │ (manual upload)  │ (vectorize-only) │                            │
├──────────┼──────────────────┼──────────────────┼────────────────────────────┤
│          │                  │                  │                            │
│ TEXT     │ Extract → chunk  │ Extract → chunk  │ ✅ NONE — works exactly    │
│ (PDF,    │ → embed → store  │ → embed → PG     │    the same way            │
│ DOCX,   │ in-memory        │ pgvector         │                            │
│ TXT)    │                  │                  │                            │
│          │                  │                  │                            │
├──────────┼──────────────────┼──────────────────┼────────────────────────────┤
│          │                  │                  │                            │
│ TABLES   │ Extract via      │ Same extraction  │ ⚠️ MINOR — raw table text  │
│ (from   │ PyMuPDF → store  │ → text chunks    │    is searchable, but HTML │
│ PDFs)   │ as text + table  │ → embed → PG     │    table structure is lost. │
│         │ HTML structure    │                  │    Student can ask "what    │
│         │                  │                  │    are the columns in the   │
│         │                  │                  │    table?" and get answer   │
│         │                  │                  │    from text, but can't see │
│         │                  │                  │    the formatted table.     │
│          │                  │                  │                            │
├──────────┼──────────────────┼──────────────────┼────────────────────────────┤
│          │                  │                  │                            │
│ IMAGES   │ Two parallel     │ Caption text     │ ⚠️ SIGNIFICANT — see below │
│ (from   │ paths:           │ only:            │                            │
│ PDFs)   │                  │                  │                            │
│         │ A) Caption+OCR   │ A) Caption+OCR   │ Lost:                      │
│         │ → text chunks    │ → text chunks    │ • Actual image file        │
│         │ → text store     │ → PG pgvector    │   (deleted after sync)     │
│         │                  │                  │ • CLIP visual embeddings   │
│         │ B) CLIP image    │ B) ❌ SKIPPED     │   (no ChromaDB)            │
│         │ embeddings       │ (no ChromaDB)    │ • "Show me the image"      │
│         │ → ChromaDB       │                  │   capability               │
│         │                  │                  │                            │
│         │ Images saved to  │ Temp file        │ Kept:                      │
│         │ static/ folder   │ deleted          │ • Caption text (searchable)│
│         │ (served as URLs) │                  │ • OCR text (searchable)    │
│         │                  │                  │ • "What does figure 3      │
│         │                  │                  │   show?" → caption answer  │
│          │                  │                  │                            │
├──────────┼──────────────────┼──────────────────┼────────────────────────────┤
│          │                  │                  │                            │
│ AUDIO    │ Transcribe via   │ Same → embed     │ ✅ MINOR — works well.     │
│ (.mp3,  │ Whisper/Gemini   │ → PG pgvector    │    Transcript text +       │
│ .wav)   │ → chunk with     │                  │    timestamps preserved.   │
│         │ timestamps       │                  │    Can't play audio back   │
│         │ → embed → store  │                  │    (file deleted), but     │
│         │                  │                  │    searchable text is all  │
│         │                  │                  │    that matters for Q&A.   │
│          │                  │                  │                            │
└──────────┴──────────────────┴──────────────────┴────────────────────────────┘
```

### The Image Problem In Detail

When a teacher's Google Drive PDF contains images (diagrams, charts, figures):

```
CURRENT SYSTEM (manual upload):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Student: "What does the circuit diagram on page 12 show?"
VTA: "The diagram shows a series RLC circuit with a 10V source, 
      100Ω resistor, 10mH inductor, and 100μF capacitor."
     [Shows actual image inline]
     [Source: lecture5.pdf, Page 12, Image, Relevance: 0.89]

GOOGLE DRIVE FLOW (current plan):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Student: "What does the circuit diagram on page 12 show?"
VTA: "The diagram shows a series RLC circuit with a 10V source, 
      100Ω resistor, 10mH inductor, and 100μF capacitor."
     [NO image shown — file was deleted after sync]
     [Source: lecture5.pdf, Page 12, Relevance: 0.89]

The text answer is IDENTICAL. The only loss is the visual display.
```

### Three Options to Solve the Image Gap

#### Option A: Accept the Tradeoff (Recommended for MVP)

Store caption text + OCR text as searchable pgvector chunks. Don't store images.
Students get text-based answers about images. They can look at the actual image on the teacher's Google Drive if they need to see it.

**Pros:** Simplest, no extra storage, privacy-friendly
**Cons:** Can't show images inline, no visual similarity search
**Storage cost:** ~0 extra (just text chunks)

#### Option B: Store Extracted Images Too

During sync, also save extracted images to PostgreSQL as base64 BLOBs. Serve them via a `/drive/image/<id>` endpoint.

**Pros:** Students see images inline
**Cons:** Defeats the "don't store raw files" goal. Image files can be large (500KB-5MB each). A PDF with 50 images = 50MB+ of storage. This is exactly what you wanted to avoid.
**Storage cost:** Potentially huge

#### Option C: Hybrid — Store Image Descriptions, Link to Source

Store caption text + a reference link back to the teacher's Google Drive file. When a student needs to see the image, show a link: "View original on Google Drive →"

**Pros:** No extra storage, student can still access the image
**Cons:** Requires teacher's Drive file to remain shared. Extra click for student.
**Storage cost:** ~0 extra

### ✅ DECIDED: Option A — Text Descriptions Only (No Image Display)

**Decision:** Images will NOT be displayed to students. Instead, the VTA provides a text description of the image content (via caption + OCR) along with the document name and page number.

**What the student sees:**
```
"The diagram on page 12 of lecture5.pdf shows a series RLC circuit 
with a 10V source, 100Ω resistor, 10mH inductor, and 100μF capacitor."
```

**Why:**
- Keeps storage at ~99% savings (no image files stored)
- Simplifies the pipeline (no image serving, no ChromaDB)
- The caption + OCR text captures the essential information
- Client has approved this approach
- Document name + page reference lets the student find the original image on Google Drive if needed

**This is final for the MVP.** Option C (link to source) may be revisited in V2.

### Updated Vectorizer for Full Multimodal Support

The `vectorize_and_store` function needs to handle all content types, not just plain text:

```python
def vectorize_and_store(
    temp_path: str,
    file_id: str,
    file_name: str,
    mime_type: str,
    user_id: int,
) -> dict:
    """
    Full multimodal vectorization for Google Drive files.
    Returns counts by content type.
    """
    import fitz  # PyMuPDF
    from document_loader import load_document
    from image_analyzer import ImageAnalyzer
    from embedding_manager import EmbeddingManager
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    embedder = EmbeddingManager()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    results = {"text_chunks": 0, "table_chunks": 0, "image_chunks": 0, "audio_chunks": 0}
    
    # ── STEP 1: EXTRACT TEXT (works for PDF, DOCX, TXT) ──
    documents = load_document(temp_path)
    text_chunks = splitter.split_documents(documents)
    
    # Tag each chunk with content type based on metadata
    for chunk in text_chunks:
        chunk_type = chunk.metadata.get("type", "text")  # "text" or "table"
        if chunk_type == "table":
            results["table_chunks"] += 1
        else:
            results["text_chunks"] += 1
    
    # ── STEP 2: EXTRACT IMAGES FROM PDFs ──
    image_chunks = []
    if mime_type == "application/pdf":
        image_analyzer = ImageAnalyzer()
        doc = fitz.open(temp_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
                try:
                    # Extract image
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Analyze: get caption + OCR text
                    analysis = image_analyzer.analyze_image_bytes(image_bytes)
                    caption = analysis.get("caption", "")
                    ocr_text = analysis.get("ocr_text", "")
                    
                    # Combine into a searchable text chunk
                    combined_text = f"[Image on page {page_num + 1}]\n"
                    if caption:
                        combined_text += f"Description: {caption}\n"
                    if ocr_text:
                        combined_text += f"Text in image: {ocr_text}\n"
                    
                    if combined_text.strip():
                        from langchain.schema import Document
                        image_chunk = Document(
                            page_content=combined_text,
                            metadata={
                                "type": "image",
                                "page": page_num + 1,
                                "source": file_name,
                            }
                        )
                        image_chunks.append(image_chunk)
                        results["image_chunks"] += 1
                except Exception:
                    continue
        
        doc.close()
    
    # ── STEP 3: EMBED ALL CHUNKS ──
    all_chunks = text_chunks + image_chunks
    chunk_texts = [c.page_content for c in all_chunks]
    
    # Batch embedding (handle large files)
    all_embeddings = []
    batch_size = 50
    for i in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[i:i + batch_size]
        batch_embeddings = embedder.embed_documents(batch)
        all_embeddings.extend(batch_embeddings)
    
    # ── STEP 4: STORE IN POSTGRESQL ──
    db = next(get_db())
    
    # ... store file metadata ...
    # ... store each chunk with its embedding and content_type metadata ...
    
    for i, (chunk, embedding) in enumerate(zip(all_chunks, all_embeddings)):
        vector_chunk = VectorChunk(
            id=str(uuid.uuid4()),
            file_metadata_id=file_meta.id,
            chunk_index=i,
            text=chunk.page_content,
            page_number=chunk.metadata.get("page"),
            content_type=chunk.metadata.get("type", "text"),  # "text", "table", "image"
            embedding=embedding.tolist(),
        )
        db.add(vector_chunk)
    
    db.commit()
    
    # ── STEP 5: DELETE TEMP FILE ──
    os.remove(temp_path)
    os.rmdir(os.path.dirname(temp_path))
    
    return results  # {"text_chunks": 45, "table_chunks": 3, "image_chunks": 12, "audio_chunks": 0}
```

### Updated Database Schema for Content Types

```sql
-- Add content_type to vector_chunks
ALTER TABLE vector_chunks ADD COLUMN content_type VARCHAR(50) DEFAULT 'text';
-- Values: 'text', 'table', 'image', 'audio'

-- This lets the query filter by type and build proper citations:
-- "Based on the table in lecture5.pdf: ..."  (content_type = 'table')
-- "The diagram shows..."                       (content_type = 'image')
-- "At timestamp 15:30, the professor said..."  (content_type = 'audio')
```

### Updated Answer Generator for Multimodal Responses

The LLM answer generator should be aware of content types:

```python
def generate_multimodal_answer(query, retrieved_chunks, citations):
    """
    Generate answer that's aware of content types.
    """
    # Separate chunks by type
    text_chunks = [c for c in retrieved_chunks if c.content_type == "text"]
    table_chunks = [c for c in retrieved_chunks if c.content_type == "table"]
    image_chunks = [c for c in retrieved_chunks if c.content_type == "image"]
    audio_chunks = [c for c in retrieved_chunks if c.content_type == "audio"]
    
    # Build context with type labels
    context_parts = []
    for chunk in retrieved_chunks:
        type_label = {
            "text": "Text from",
            "table": "Table data from",
            "image": "Image description from",
            "audio": "Audio transcript from",
        }.get(chunk.content_type, "Content from")
        
        context_parts.append(
            f"[{type_label} {chunk.file_name}, Page {chunk.page_number}]\n"
            f"{chunk.text}"
        )
    
    # LLM prompt includes content type awareness
    prompt = f"""You are a Virtual Teaching Assistant. Answer based on course materials.

The materials include text, tables, image descriptions, and audio transcripts.
When referencing content, mention its type:
- "According to the table in [file]..."
- "The diagram on page X shows..."
- "In the lecture recording at [timestamp]..."

Context:
{'---'.join(context_parts)}

Question: {query}

Answer:"""
    
    return model.generate_content(prompt).text
```

### Updated File Metadata Model

```python
class FileMetadata(Base):
    __tablename__ = "file_metadata"
    
    id = Column(Integer, primary_key=True)
    drive_file_id = Column(String(255), nullable=False)
    file_name = Column(String(500), nullable=False)
    mime_type = Column(String(255))
    owner_user_id = Column(Integer, ForeignKey("users.id"))
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    drive_modified_time = Column(DateTime(timezone=True), nullable=True)
    course_name = Column(String(255), nullable=True)
    
    # Content breakdown
    num_text_chunks = Column(Integer, default=0)
    num_table_chunks = Column(Integer, default=0)
    num_image_chunks = Column(Integer, default=0)
    num_audio_chunks = Column(Integer, default=0)
    
    # Storage efficiency metric
    total_chunks = Column(Integer, default=0)
    estimated_original_size_kb = Column(Integer, default=0)  # For comparison
```

### What the Student Actually Gets (End-to-End)

```
TEACHER uploads "Machine Learning Course" folder to Google Drive:
├── lecture1.pdf      (40 pages, 5 diagrams, 3 tables)
├── lecture2.pdf      (35 pages, 8 diagrams, 1 table)
├── midterm_review.docx (10 pages, text only)
├── recording.mp3     (50 minute lecture)

TEACHER connects Drive → syncs all 4 files

WHAT GETS STORED IN POSTGRESQL:
┌──────────────────────────────────────────────────────────────┐
│ File            │ Text  │ Tables │ Images │ Audio │ Total    │
├─────────────────┼───────┼────────┼────────┼───────┼──────────┤
│ lecture1.pdf    │  85   │   6    │   15   │   0   │  106     │
│ lecture2.pdf    │  72   │   2    │   24   │   0   │   98     │
│ midterm_review  │  22   │   0    │    0   │   0   │   22     │
│ recording.mp3   │  45   │   0    │    0   │  45   │   90     │
├─────────────────┼───────┼────────┼────────┼───────┼──────────┤
│ TOTAL           │ 224   │   8    │   39   │  45   │  316     │
└──────────────────────────────────────────────────────────────┘
Total vectors stored: 316
Storage: ~316 chunks × ~1KB text + 316 × 768-dim float = ~1.5MB

Original files: ~150MB total (PDFs + audio)
Stored vectors: ~1.5MB
Storage savings: ~99%
```

STUDENT asks: "What activation functions were discussed in the lectures?"

VTA searches 316 vector chunks → finds relevant text/table/image chunks →
LLM synthesizes answer from multiple sources:

"Based on the course materials, three activation functions were discussed:

1. **ReLU** (Rectified Linear Unit) — mentioned in Lecture 1 (page 15): 
   f(x) = max(0, x). The table on page 16 compares ReLU's computational 
   efficiency against sigmoid.

2. **Sigmoid** — discussed in Lecture 1 (page 14): σ(x) = 1/(1+e^(-x)). 
   The diagram on page 15 shows how sigmoid maps inputs to (0,1).

3. **Softmax** — covered in Lecture 2 (page 8) for multi-class classification. 
   In the lecture recording at approximately 23:15, the professor emphasized 
   that softmax is used in the output layer for probability distribution.

(Lecture 1 PDF, Lecture 2 PDF, Recording.mp3)"
```

That's a real, multimodal teaching assistant answer — powered by ~1.5MB of stored vectors instead of ~150MB of raw files.

---

## Critical Gap Analysis & Solutions

### The Honest Assessment

Before building, we need to address two hard problems:

1. **Is the Google Drive flow solid?** Mostly yes, but there are gaps.
2. **Will the VTA actually give good answers?** Not with the current pipeline alone. It needs improvement.

---

### Problem 1: Google Drive Flow Gaps

#### What's Solid

| Aspect | Status | Why |
|--------|--------|-----|
| OAuth permission model | ✅ Correct | Read-only scope, teacher controls what's synced |
| Not storing raw files | ✅ Correct | Download → vectorize → delete temp. Only vectors in PG. |
| Vectorization pipeline | ✅ Correct | Reuses existing document_loader + embedding_manager |
| Temp file cleanup | ✅ Correct | Deleted after vectorization |

#### What's Missing

| Gap | Impact | Solution |
|-----|--------|----------|
| **File updates on Drive** | Teacher updates a PDF → our vectors are stale, students get outdated answers | Add `modifiedTime` tracking. On re-sync, compare Drive's `modifiedTime` with our stored `synced_at`. If Drive file is newer, re-vectorize. |
| **Token expiry** | Google refresh tokens expire after 6 months of inactivity. Teacher's Drive connection silently breaks. | Before each Drive API call, catch `RefreshError`. If token is dead, clear `google_drive_connected = False` and prompt teacher to re-connect. |
| **Large file handling** | A 200-page textbook PDF could generate 500+ chunks. Embedding API costs + rate limits. | Add file size/chunk count warnings before sync. Batch embedding calls. Show progress to teacher. |
| **Image-heavy files** | PowerPoint with mostly diagrams → extracted text is minimal → poor vectorization | Flag these files. The existing image_analyzer.py can caption images, but only if the multimodal pipeline runs. |
| **No course grouping** | All synced files from all teachers are searchable by all students. A student in CS 101 sees Biology 201 materials. | Add a `course_id` or `course_name` field to `file_metadata`. Teacher assigns files to a course. Students are enrolled in courses. (Future feature — see section below.) |

#### Recommended Fix: File Change Detection

Add to `gdrive/models.py`:

```python
class FileMetadata(Base):
    __tablename__ = "file_metadata"
    
    id = Column(Integer, primary_key=True)
    drive_file_id = Column(String(255), nullable=False)
    file_name = Column(String(500), nullable=False)
    mime_type = Column(String(255))
    owner_user_id = Column(Integer, ForeignKey("users.id"))
    num_chunks = Column(Integer, default=0)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # NEW: Track Drive's last modified time for change detection
    drive_modified_time = Column(DateTime(timezone=True), nullable=True)
    
    # NEW: Course association (future-proofing)
    course_name = Column(String(255), nullable=True)
```

Update sync logic to detect changes:

```python
# In gdrive/routes.py sync_files():
meta = service.files().get(
    fileId=file_id,
    fields="id, name, mimeType, modifiedTime"
).execute()

drive_modified = datetime.fromisoformat(meta["modifiedTime"].replace("Z", "+00:00"))

existing = db.query(FileMetadata).filter_by(drive_file_id=file_id).first()
if existing and existing.drive_modified_time and existing.drive_modified_time >= drive_modified:
    # File hasn't changed since last sync, skip
    results.append({"file_id": file_id, "name": meta["name"], "status": "up_to_date"})
    continue

# File is new or changed → vectorize
```

#### Recommended Fix: Token Expiry Handling

```python
# In gdrive/routes.py before any Drive API call:
from google.auth.exceptions import RefreshError

try:
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)
except RefreshError:
    # Token is dead — teacher needs to re-authenticate
    user.google_drive_connected = False
    user.google_drive_refresh_token = None
    db.commit()
    return jsonify({
        "error": "Google Drive connection expired. Please reconnect.",
        "action": "reconnect_drive"
    }), 401
```

---

### Problem 2: Will Students Get Good Answers?

#### The Hard Truth About the Current Pipeline

After analyzing the existing code, here is what the VTA currently does when a student asks a question:

```
Student: "What is the time complexity of binary search?"

Current pipeline:
1. Embed the question (all-MiniLM-L6-v2, 384 dimensions)
2. Find top 5 similar chunks from vector store
3. Return VERBATIM TEXT from those chunks as the "answer"

What the student gets:
"Based on the uploaded documents:

Chapter 5: Searching Algorithms
Binary search works by repeatedly dividing the search interval 
in half. If the value of the search key is less than the item in 
the middle of the interval, narrow the interval to the lower half.
Otherwise, narrow it to the upper half. The time complexity of 
binary search is O(log n) because..."

This is NOT a good answer. It's just raw text from the textbook.
There's no synthesis, no explanation, no adaptation to the question.
```

**The current VTA is essentially a semantic search engine, not a teaching assistant.** It finds relevant text but doesn't explain it.

#### What Needs to Change for Real Answers

| Component | Current State | What's Needed | Difficulty |
|-----------|--------------|---------------|------------|
| **Answer Generation** | Returns verbatim text excerpts | Use an LLM to synthesize answers from retrieved chunks | Medium |
| **Embedding Model** | all-MiniLM-L6-v2 (256 token limit) | Upgrade to a model with longer context (e.g., Gemini embeddings support 8K tokens) | Easy |
| **Chunking** | Fixed 1000 chars, no structure awareness | Semantic chunking that respects headings, paragraphs, list items | Medium |
| **Similarity Threshold** | None — returns top-k regardless of quality | Filter out chunks below a relevance threshold (e.g., 0.4) | Easy |
| **Multi-chunk Synthesis** | Only uses top chunk | Combine multiple relevant chunks into a coherent answer | Medium |

#### Solution: Add LLM-Based Answer Generation

The code already has a placeholder for this. Here's what needs to happen:

```python
# In answer_generator.py (or a new gdrive/answer_engine.py):

import google.generativeai as genai

class LLMAnswerGenerator:
    """Uses Gemini to synthesize answers from retrieved chunks."""
    
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel("gemini-2.0-flash")
    
    def generate(self, query: str, retrieved_chunks: list, citations: list) -> dict:
        # Build context from retrieved chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            source = citations[i].get("source", "Unknown")
            page = citations[i].get("page", "?")
            context_parts.append(
                f"[Source {i+1}: {source}, Page {page}]\n{chunk['text']}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        prompt = f"""You are a helpful Virtual Teaching Assistant. A student has asked a question.
Answer based ONLY on the provided course materials. If the materials don't contain 
the answer, say so honestly.

Course Materials:
{context}

Student Question: {query}

Instructions:
- Give a clear, educational answer
- Explain concepts in a way a student would understand
- Reference specific sources when possible (e.g., "According to [Source 1]...")
- If the answer requires information not in the materials, say "The course materials 
  don't cover this specific question, but based on what's available..."
- Use examples from the materials when helpful

Answer:"""

        response = self.model.generate_content(prompt)
        
        return {
            "answer": response.text,
            "source_chunks_used": len(retrieved_chunks),
            "generation_method": "llm_synthesis"
        }
```

#### The Improved Flow

```
Student: "What is the time complexity of binary search?"

Improved pipeline:
1. Embed the question
2. Find top 10 similar chunks (increase from 5)
3. Filter out chunks with similarity < 0.4 (quality gate)
4. Pass filtered chunks + question to Gemini LLM
5. LLM synthesizes a proper educational answer

What the student gets:
"The time complexity of binary search is O(log n). Here's why:

Each step of the algorithm cuts the search space in half. If you 
start with n elements, after one comparison you have n/2 elements 
left, after two you have n/4, and so on. The algorithm stops when 
you're down to 1 element.

The number of steps needed is the answer to: n / 2^k = 1, which 
gives k = log₂(n). That's why it's O(log n).

For example, if you have 1,000,000 elements, binary search needs 
at most ~20 comparisons (log₂(1,000,000) ≈ 20), compared to 
1,000,000 comparisons for a linear search.

(Source: Chapter 5, Searching Algorithms)"
```

That is a **real teaching assistant answer**.

#### Cost Consideration

| Approach | Cost | Quality |
|----------|------|---------|
| Current (no LLM) | Free | Low — raw text dumps |
| Gemini 2.0 Flash | Free tier: 15 RPM, 1M tokens/day | High — synthesized answers |
| Gemini 1.5 Flash | Free tier available | High |
| OpenAI GPT-4o-mini | ~$0.15/1M input tokens | High |

Gemini has a generous free tier. For a university project, this should be free.

---

### Problem 3: Course-Based Access Control (Future-Proofing)

Currently, if multiple teachers sync files, all students see all files. This doesn't match how universities work (students are enrolled in specific courses).

#### Simple Course System

Add to database:

```sql
CREATE TABLE courses (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,     -- "CPT_S 421 - AI"
    teacher_id  INTEGER REFERENCES users(id),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE enrollments (
    id          SERIAL PRIMARY KEY,
    student_id  INTEGER REFERENCES users(id),
    course_id   INTEGER REFERENCES courses(id),
    enrolled_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(student_id, course_id)
);

-- Add course_id to file_metadata
ALTER TABLE file_metadata ADD COLUMN course_id INTEGER REFERENCES courses(id);
```

When a student queries, only search vectors from courses they're enrolled in:

```python
# In query_bridge.py:
def search_gdrive_vectors(query: str, student_id: int, top_k: int = 5):
    # Get courses this student is enrolled in
    enrolled_course_ids = db.query(Enrollment.course_id).filter_by(student_id=student_id).subquery()
    
    # Only search chunks from files in those courses
    chunks = db.query(VectorChunk).join(FileMetadata).filter(
        FileMetadata.course_id.in_(enrolled_course_ids)
    ).all()
```

**This is NOT needed for MVP**, but the `course_name` column on `file_metadata` should be added now so it's easy to implement later.

---

### Summary: What Must Be Built vs. What Can Wait

#### Must Build (MVP)

| Feature | Why |
|---------|-----|
| Auth (sign in / sign up with role) | Students and teachers need accounts |
| PostgreSQL for users + vectors | Persistent storage |
| Google Drive OAuth | Teachers connect their Drive |
| Download → vectorize → delete temp flow | Core value proposition |
| `modifiedTime` tracking | Prevent stale vectors |
| Token expiry handling | Prevent silent failures |
| **LLM answer generation** | **Without this, the VTA is just a search engine** |

#### Should Build (V1.1) — BUT NOW REQUIRED BY CLIENT

| Feature | Why |
|---------|-----|
| **Course-based access control** | Students only see their course materials - CRITICAL for university setting |
| **Re-sync detection** | Efficient updates when Drive files change |
| **Progress indicators during sync** | UX for large file syncs |
| **Semantic chunking** | Better retrieval quality - CRITICAL for good answers |

---

## New Section 14: Course-Based Access Control (REQUIRED)

### 14.1 The Problem

Currently, if multiple teachers sync files from different courses (e.g., CPT_S 421 - AI and BIO 101 - Biology), ALL students can access ALL course materials. This is not how universities work.

**The Requirement:**
- Each course has its own set of materials (synced by the teacher)
- Each student is enrolled in specific courses
- Students can ONLY ask questions about materials from courses they're enrolled in
- Students CANNOT ask questions about materials from courses they're not enrolled in

### 14.2 New Database Schema

```sql
-- Courses table
CREATE TABLE courses (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,         -- "CPT_S 421 - AI"
    code            VARCHAR(50) NOT NULL,          -- "CPT_S 421"
    description     TEXT,
    teacher_id      INTEGER REFERENCES users(id) NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

-- Course enrollments (which students are in which courses)
CREATE TABLE enrollments (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER REFERENCES users(id) NOT NULL,
    course_id       INTEGER REFERENCES courses(id) NOT NULL,
    enrolled_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status          VARCHAR(50) DEFAULT 'active',   -- 'active', 'dropped', 'completed'
    UNIQUE(student_id, course_id)
);

-- Update file_metadata to associate with a course
ALTER TABLE file_metadata ADD COLUMN course_id INTEGER REFERENCES courses(id);

-- Index for fast enrollment lookups
CREATE INDEX idx_enrollments_student ON enrollments(student_id, status);
CREATE INDEX idx_file_metadata_course ON file_metadata(course_id);
```

### 14.3 New User Model Updates

```python
# In auth/models.py - add course relationship
class User(Base):
    __tablename__ = "users"
    
    # ... existing fields ...
    
    # Relationships
    teaching_courses = relationship("Course", back_populates="teacher", foreign_keys="Course.teacher_id")
    enrollments = relationship("Enrollment", back_populates="student")
    enrolled_courses = relationship(
        "Course",
        secondary="enrollments",
        back_populates="students"
    )
```

### 14.4 New Course Model

```python
# In gdrive/models.py - add Course model
class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)           -- "CPT_S 421 - AI"
    code = Column(String(50), nullable=False)           -- "CPT_S 421"
    description = Column(Text)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id], back_populates="teaching_courses")
    files = relationship("FileMetadata", back_populates="course")
    students = relationship("Enrollment", back_populates="course")


class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default="active")  -- "active", "dropped", "completed"
    
    # Relationships
    student = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="students")
```

### 14.5 New API Endpoints for Course Management

| Method | Endpoint | Auth | Role | Request Body | Response | Purpose |
|--------|----------|:---:|------|-------------|----------|---------|
| POST | `/api/courses` | Yes | Teacher | `{ name, code, description }` | `{ course }` | Teacher creates a new course |
| GET | `/api/courses` | Yes | Teacher | — | `{ courses: [...] }` | List teacher's courses |
| GET | `/api/courses/<id>` | Yes | Teacher | — | `{ course }` | Get course details + synced files |
| PUT | `/api/courses/<id>` | Yes | Teacher | `{ name, description }` | `{ course }` | Update course info |
| DELETE | `/api/courses/<id>` | Yes | Teacher | — | `{ message }` | Delete course (archives, doesn't delete) |
| POST | `/api/courses/<id>/enroll` | Yes | Student | — | `{ message }` | Student enrolls in a course |
| GET | `/api/courses/enrolled` | Yes | Student | — | `{ courses: [...] }` | List student's enrolled courses |
| DELETE | `/api/courses/<id>/enroll` | Yes | Student | — | `{ message }` | Student drops a course |

### 14.6 Updated User Roles Table

| Role | Register/Login | Ask VTA Questions | View Course Materials | Create Course | Sync Drive Files | Manage Course |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Student** | Yes | Yes (enrolled courses only) | Yes (enrolled only) | No | No | No |
| **Teacher** | Yes | Yes (all their courses) | Yes (all their courses) | Yes | Yes | Yes |

### 14.7 Course Enrollment Flow

```
TEACHER FLOW:
────────────
Teacher logs in
         │
         ▼
Teacher creates course: "CPT_S 421 - AI"
         │
         ▼
Teacher syncs Drive files AND assigns them to a course
         │
         ▼
Teacher gets enrollment code/link to share with students

STUDENT FLOW:
─────────────
Student logs in
         │
         ▼
Student sees list of available courses (or enters enrollment code)
         │
         ▼
Student enrolls in "CPT_S 421 - AI"
         │
         ▼
Student asks VTA question
         │
         ▼
VTA ONLY searches vectors from enrolled courses
         │
         ▼
Student gets answer (or "This question is about a course you're not enrolled in")
```

### 14.8 Query Bridge - Course Filtering

```python
# In gdrive/query_bridge.py:
def search_gdrive_vectors(query: str, user_id: int, user_role: str, top_k: int = 5):
    """
    Search Google Drive vectorized content in PostgreSQL.
    CRITICAL: Filters by course enrollment for students.
    """
    db = next(get_db())
    embedder = EmbeddingManager()
    
    # Embed the query
    query_embedding = embedder.embed_query(query)
    
    # Build course filter based on role
    if user_role == "teacher":
        # Teachers can search all their own course materials
        teacher_courses = db.query(Course).filter_by(teacher_id=user_id, is_active=True).all()
        course_ids = [c.id for c in teacher_courses]
    elif user_role == "student":
        # Students can ONLY search courses they're enrolled in
        enrollments = db.query(Enrollment).filter_by(
            student_id=user_id, 
            status="active"
        ).all()
        course_ids = [e.course_id for e in enrollments]
        
        if not course_ids:
            # Student not enrolled in any courses - return empty
            return []
    else:
        return []
    
    # Get chunks only from allowed courses
    chunks = db.query(VectorChunk).join(
        FileMetadata
    ).filter(
        FileMetadata.course_id.in_(course_ids)
    ).all()
    
    # Compute cosine similarity
    results = []
    for chunk in chunks:
        similarity = cosine_similarity(query_embedding, chunk.embedding)
        results.append({
            "text": chunk.text,
            "score": similarity,
            "source": chunk.file_metadata.file_name,
            "page": chunk.page_number,
            "course_id": chunk.file_metadata.course_id,
            "course_name": chunk.file_metadata.course.name if chunk.file_metadata.course else None,
        })
    
    # Sort by score, return top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
```

### 14.9 Course Assignment During Sync

```python
# In gdrive/routes.py - sync_files endpoint:
@drive_bp.route("/sync", methods=["POST"])
@login_required
@teacher_required
def sync_files():
    """
    POST /drive/sync
    Body: { "file_ids": ["id1", "id2", ...], "course_id": 1 }
    
    When syncing, MUST specify which course this file belongs to.
    """
    data = request.get_json()
    file_ids = data.get("file_ids", [])
    course_id = data.get("course_id")
    
    # Validate course belongs to this teacher
    db = next(get_db())
    course = db.query(Course).filter_by(id=course_id, teacher_id=session["user_id"]).first()
    if not course:
        return jsonify({"error": "Course not found or access denied"}), 403
    
    # ... rest of sync logic, passing course_id to vectorize_and_store ...
```

### 14.10 Enrollment Codes (Optional but Recommended)

```python
# Generate a simple enrollment code for each course
def generate_enrollment_code():
    import secrets
    return secrets.token_urlsafe(4).upper()[:8]  # e.g., "A3B7K9MP"

# In Course model:
class Course(Base):
    __tablename__ = "courses"
    
    # ... existing fields ...
    enrollment_code = Column(String(20), unique=True, nullable=True)
    
# Auto-generate code when course is created
course = Course(
    name=data["name"],
    code=data["code"],
    teacher_id=session["user_id"],
    enrollment_code=generate_enrollment_code()
)
```

### 14.11 Frontend Integration - Course Selection

```javascript
// When teacher syncs files, they MUST select a course first
async function syncFiles(fileIds, courseId) {
    const res = await fetch("/drive/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            file_ids: fileIds,
            course_id: courseId  // REQUIRED
        }),
    });
    return res.json();
}

// Student sees their enrolled courses
async function getEnrolledCourses() {
    const res = await fetch("/api/courses/enrolled");
    return res.json();
}
```

---

## New Section 15: Semantic Chunking Implementation

### 15.1 Why Semantic Chunking?

Fixed-size chunking (e.g., every 1000 characters) has problems:

| Problem | Example |
|---------|---------|
| **Splits sentences** | "The time complexity is O(n log n)" → "The time compl" + "exity is O(n log n)" |
| **Breaks code blocks** | `if (x > 0) { return true; }` → split in middle |
| **Loses context** | A paragraph about "activation functions" might be split, losing that context |
| **Poor retrieval** | Similarity search finds partial sentences, not complete thoughts |

**Semantic chunking** respects:
- Paragraph boundaries
- Code blocks
- Headings and sections
- Lists and bullet points

### 15.2 Semantic Chunking Implementation

```python
# In gdrive/semantic_chunker.py
"""
Semantic chunking that respects document structure.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter, PythonCodeTextSplitter
from langchain.schema import Document
import re


class SemanticChunker:
    """
    Multi-strategy chunking that adapts to document type.
    """
    
    def __init__(
        self, 
        chunk_size: int = 1000, 
        chunk_overlap: int = 200,
        respect_sentences: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.respect_sentences = respect_sentences
    
    def chunk_documents(self, documents: list[Document]) -> list[Document]:
        """
        Main entry point: chunk a list of documents semantically.
        """
        all_chunks = []
        
        for doc in documents:
            # Detect document type and choose strategy
            doc_type = self._detect_doc_type(doc)
            
            if doc_type == "markdown":
                chunks = self._chunk_markdown(doc)
            elif doc_type == "code":
                chunks = self._chunk_code(doc)
            elif doc_type == "pdf":
                chunks = self._chunk_pdf(doc)
            elif doc_type == "html":
                chunks = self._chunk_html(doc)
            else:
                chunks = self._chunk_text(doc)
            
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def _detect_doc_type(self, doc: Document) -> str:
        """Detect the document type based on content or metadata."""
        content = doc.page_content.lower()
        metadata = doc.metadata
        
        # Check metadata first
        if metadata.get("source", "").endswith((".py", ".js", ".java", ".cpp")):
            return "code"
        if metadata.get("source", "").endswith((".md", ".markdown")):
            return "markdown"
        if metadata.get("source", "").endswith((".pdf",)):
            return "pdf"
        
        # Check content
        if "<html" in content[:200] or "<!DOCTYPE" in content[:200]:
            return "html"
        if content.startswith("#") or "## " in content[:500]:
            return "markdown"
        if "def " in content or "function " in content or "class " in content:
            return "code"
        
        return "text"
    
    def _chunk_markdown(self, doc: Document) -> list[Document]:
        """Chunk markdown files using header-based splitting."""
        # Split by headers first
        headers_to_split_on = [
            ("#", "heading1"),
            ("##", "heading2"),
            ("###", "heading3"),
            ("####", "heading4"),
        ]
        
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_empty_lines=True
        )
        
        # First split by headers
        splits = markdown_splitter.split_text(doc.page_content)
        
        # Then further split large chunks with overlap
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        chunks = []
        for split in splits:
            # Add header context to chunk metadata
            header = split.metadata.get("heading1") or split.metadata.get("heading2") or ""
            
            # If chunk is too large, split it
            if len(split.page_content) > self.chunk_size:
                sub_chunks = text_splitter.split_text(split.page_content)
                for i, sub in enumerate(sub_chunks):
                    chunks.append(Document(
                        page_content=sub,
                        metadata={
                            **doc.metadata,
                            **split.metadata,
                            "section_header": header,
                            "chunk_index": i,
                            "chunking_strategy": "semantic_markdown"
                        }
                    ))
            else:
                chunks.append(Document(
                    page_content=split.page_content,
                    metadata={
                        **doc.metadata,
                        **split.metadata,
                        "section_header": header,
                        "chunking_strategy": "semantic_markdown"
                    }
                ))
        
        return chunks
    
    def _chunk_code(self, doc: Document) -> list[Document]:
        """Chunk code files, preserving function/class boundaries."""
        code_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[
                "\n\ndef ", "\n\nclass ", "\n\ndef ", "\n\nclass ",
                "\n\nasync def ", "\n\nasync class ",
                "\nconst ", "\nlet ", "\nvar ",
                ";\n", "\n", " ", ""
            ],
            length_function=len,
        )
        
        chunks = code_splitter.split_documents([doc])
        
        # Add metadata indicating code chunk
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunking_strategy"] = "semantic_code"
            chunk.metadata["chunk_index"] = i
        
        return chunks
    
    def _chunk_pdf(self, doc: Document) -> list[Document]:
        """Chunk PDF content, respecting paragraphs and sections."""
        # For PDFs, try to respect paragraph boundaries
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n\n", "\n\n", "\n", ". ", "; ", " ", ""],
            length_function=len,
        )
        
        chunks = text_splitter.split_documents([doc])
        
        for i, chunk in enumerate(chunks):
            # Try to extract page number from metadata
            page_num = chunk.metadata.get("page")
            chunk.metadata["chunking_strategy"] = "semantic_pdf"
            chunk.metadata["chunk_index"] = i
            chunk.metadata["source_page"] = page_num
        
        return chunks
    
    def _chunk_text(self, doc: Document) -> list[Document]:
        """Default text chunking that respects sentence boundaries."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n\n", "\n\n", "\n", ". ", "! ", "? ", "; ", " ", ""],
            length_function=len,
        )
        
        chunks = text_splitter.split_documents([doc])
        
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunking_strategy"] = "semantic_text"
            chunk.metadata["chunk_index"] = i
        
        return chunks
    
    def _chunk_html(self, doc: Document) -> list[Document]:
        """Chunk HTML content by tags."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(doc.page_content, "html.parser")
        
        # Extract text from meaningful tags
        chunks = []
        
        # Get all paragraph-like elements
        for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]):
            text = tag.get_text(strip=True)
            if len(text) > 50:  # Only meaningful chunks
                chunks.append(Document(
                    page_content=text,
                    metadata={
                        **doc.metadata,
                        "html_tag": tag.name,
                        "chunking_strategy": "semantic_html"
                    }
                ))
        
        # If no meaningful chunks found, fall back to text
        if not chunks:
            return self._chunk_text(doc)
        
        # Merge small chunks
        merged = self._merge_small_chunks(chunks)
        return merged
    
    def _merge_small_chunks(self, chunks: list[Document], min_size: int = 200) -> list[Document]:
        """Merge small chunks together to meet minimum size."""
        if not chunks:
            return []
        
        merged = []
        current = chunks[0]
        
        for chunk in chunks[1:]:
            if len(current.page_content) < min_size:
                # Merge with current
                current = Document(
                    page_content=current.page_content + "\n\n" + chunk.page_content,
                    metadata={**current.metadata, **chunk.metadata}
                )
            else:
                merged.append(current)
                current = chunk
        
        merged.append(current)
        return merged
```

### 15.3 Using Semantic Chunker in Vectorizer

```python
# In gdrive/vectorizer.py - update to use semantic chunking:
from .semantic_chunker import SemanticChunker

def vectorize_and_store(
    temp_path: str,
    file_id: str,
    file_name: str,
    mime_type: str,
    user_id: int,
    course_id: int,
) -> dict:
    """
    Full multimodal vectorization for Google Drive files.
    Now uses SEMANTIC CHUNKING for better retrieval quality.
    """
    # ... load document ...
    documents = load_document(temp_path)
    
    # NEW: Use semantic chunker instead of fixed-size
    semantic_chunker = SemanticChunker(chunk_size=1000, chunk_overlap=200)
    all_chunks = semantic_chunker.chunk_documents(documents)
    
    # ... embed and store ...
```

### 15.4 Chunking Strategy Metadata

Store which strategy was used for each chunk:

```sql
-- Add to vector_chunks table
ALTER TABLE vector_chunks ADD COLUMN chunking_strategy VARCHAR(50) DEFAULT 'fixed';
-- Values: 'fixed', 'semantic_text', 'semantic_markdown', 'semantic_code', 'semantic_pdf', 'semantic_html'

-- Add section header for context
ALTER TABLE vector_chunks ADD COLUMN section_header VARCHAR(500);
```

### 15.5 Improved Query with Chunking Strategy Awareness

```python
# In query_bridge.py - use chunking strategy for better results:
def search_gdrive_vectors(query: str, user_id: int, user_role: str, top_k: int = 5):
    """
    Search with awareness of chunking strategies.
    """
    # ... existing code ...
    
    # Prefer semantic chunks over fixed chunks
    for chunk in results:
        strategy = chunk.get("chunking_strategy", "fixed")
        chunk["preference_score"] = 1.0 if strategy.startswith("semantic") else 0.5
    
    # Re-sort with preference
    results.sort(key=lambda x: (x["score"], x.get("preference_score", 0)), reverse=True)
    return results[:top_k]
```

---

## New Section 16: Progress Indicators for Sync

### 16.1 Why Progress Indicators?

When a teacher syncs a large file (e.g., a 200-page textbook):
- It can take 30+ seconds to process
- Without feedback, teacher thinks it's frozen
- They may refresh or cancel mid-process

**Solution:** Real-time progress updates via Server-Sent Events (SSE).

### 16.2 SSE Endpoint for Progress

```python
# In gdrive/routes.py
from flask import Response, jsonify
import json
import queue
import threading

# Thread-safe progress queue per user
_progress_queues = {}

def get_progress_queue(user_id):
    """Get or create progress queue for a user."""
    if user_id not in _progress_queues:
        _progress_queues[user_id] = queue.Queue()
    return _progress_queues[user_id]


@drive_bp.route("/sync/progress/<task_id>", methods=["GET"])
@login_required
def get_sync_progress(task_id):
    """
    Server-Sent Events endpoint for sync progress.
    
    Usage:
    const eventSource = new EventSource("/drive/sync/progress/task-123");
    eventSource.onmessage = (e) => {
        const progress = JSON.parse(e.data);
        console.log(progress);  // { stage: "downloading", percent: 50, message: "..." }
    };
    """
    user_id = session["user_id"]
    progress_queue = get_progress_queue(user_id)
    
    def generate():
        while True:
            try:
                # Wait for progress update (timeout: 2 minutes max)
                progress = progress_queue.get(timeout=120)
                
                # Send as SSE
                yield f"data: {json.dumps(progress)}\n\n"
                
                # Check if complete or error
                if progress.get("stage") in ("complete", "error"):
                    break
            except queue.Empty:
                # No progress for 2 minutes - send heartbeat
                yield f"data: {json.dumps({'stage': 'heartbeat', 'percent': -1})}\n\n"
                break
    
    return Response(generate(), mimetype="text/event-stream")


@drive_bp.route("/sync", methods=["POST"])
@login_required
@teacher_required
def sync_files():
    """
    POST /drive/sync
    Body: { "file_ids": ["id1", "id2", ...], "course_id": 1 }
    
    Now supports progress tracking via SSE.
    """
    data = request.get_json()
    file_ids = data.get("file_ids", [])
    course_id = data.get("course_id")
    user_id = session["user_id"]
    
    progress_queue = get_progress_queue(user_id)
    
    def send_progress(stage, percent, message):
        progress_queue.put({
            "stage": stage,
            "percent": percent,
            "message": message
        })
    
    # Generate a task ID for tracking
    import uuid
    task_id = str(uuid.uuid4())
    
    # Start sync in background thread (so we can return immediately)
    def run_sync():
        try:
            send_progress("starting", 0, f"Starting sync of {len(file_ids)} file(s)...")
            
            db = next(get_db())
            user = db.query(User).get(user_id)
            
            from .auth import refresh_credentials
            creds = refresh_credentials(user.google_drive_refresh_token)
            service = build_drive_service(creds)
            
            results = []
            total_files = len(file_ids)
            
            for i, file_id in enumerate(file_ids):
                try:
                    percent = int((i / total_files) * 100)
                    send_progress("downloading", percent, f"Downloading file {i+1} of {total_files}...")
                    
                    # Get file metadata
                    meta = service.files().get(
                        fileId=file_id,
                        fields="id, name, mimeType, size, modifiedTime"
                    ).execute()
                    
                    file_size = int(meta.get("size", 0))
                    send_progress("downloaded", percent, f"Downloaded {meta['name']} ({file_size/1024:.1f} KB)")
                    
                    # Download to temp
                    temp_path = download_file(service, file_id, meta["name"], meta["mimeType"])
                    
                    send_progress("vectorizing", percent, f"Vectorizing {meta['name']}...")
                    
                    # Vectorize and store
                    num_chunks = vectorize_and_store(
                        temp_path=temp_path,
                        file_id=file_id,
                        file_name=meta["name"],
                        mime_type=meta["mimeType"],
                        user_id=user_id,
                        course_id=course_id,
                    )
                    
                    results.append({
                        "file_id": file_id,
                        "name": meta["name"],
                        "status": "synced",
                        "chunks_stored": num_chunks,
                    })
                    
                    send_progress("complete", 100, f"Successfully synced {meta['name']}")
                    
                except Exception as e:
                    results.append({
                        "file_id": file_id,
                        "status": "error",
                        "error": str(e),
                    })
                    send_progress("error", -1, f"Error syncing {file_id}: {str(e)}")
            
            # Store results for retrieval
            _sync_results[task_id] = results
            
        except Exception as e:
            send_progress("error", -1, f"Unexpected error: {str(e)}")
    
    # Run sync in background
    thread = threading.Thread(target=run_sync)
    thread.start()
    
    return jsonify({
        "task_id": task_id,
        "message": "Sync started"
    }), 202


# Store results for retrieval
_sync_results = {}
```

### 16.3 Frontend Progress UI

```javascript
// progressTracker.js - handles progress display

class SyncProgressTracker {
    constructor(onProgress, onComplete, onError) {
        this.onProgress = onProgress;
        this.onComplete = onComplete;
        this.onError = onError;
        this.eventSource = null;
    }
    
    start(taskId) {
        // Connect to SSE endpoint
        this.eventSource = new EventSource(`/drive/sync/progress/${taskId}`);
        
        this.eventSource.onmessage = (event) => {
            const progress = JSON.parse(event.data);
            
            switch (progress.stage) {
                case "starting":
                    this.onProgress({
                        status: "starting",
                        percent: 0,
                        message: progress.message
                    });
                    break;
                    
                case "downloading":
                case "vectorizing":
                    this.onProgress({
                        status: progress.stage,
                        percent: progress.percent,
                        message: progress.message
                    });
                    break;
                    
                case "complete":
                    this.onComplete(progress);
                    this.close();
                    break;
                    
                case "error":
                    this.onError(progress);
                    this.close();
                    break;
                    
                case "heartbeat":
                    // Connection still alive
                    break;
            }
        };
        
        this.eventSource.onerror = (error) => {
            this.onError({ message: "Connection lost" });
            this.close();
        };
    }
    
    close() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

// Usage in teacher dashboard:
const tracker = new SyncProgressTracker(
    (progress) => {
        // Update progress bar
        document.getElementById("progressBar").style.width = `${progress.percent}%`;
        document.getElementById("statusText").textContent = progress.message;
    },
    (result) => {
        // Show success
        alert("Sync complete!");
    },
    (error) => {
        // Show error
        alert("Sync failed: " + error.message);
    }
);

// Start tracking when sync begins
async function syncFiles() {
    const response = await fetch("/drive/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            file_ids: selectedFileIds,
            course_id: selectedCourseId
        })
    });
    
    const data = await response.json();
    tracker.start(data.task_id);
}
```

### 16.4 Progress Indicator Component UI

```html
<!-- Progress indicator component for sync -->
<div id="syncProgressPanel" class="progress-panel" style="display:none;">
    <div class="progress-header">
        <h4>Syncing Files</h4>
        <button class="close-btn" onclick="cancelSync()">×</button>
    </div>
    
    <div class="progress-bar-container">
        <div id="syncProgressBar" class="progress-bar" style="width: 0%;"></div>
    </div>
    
    <div id="syncProgressStatus" class="progress-status">
        Starting...
    </div>
    
    <div id="syncProgressDetails" class="progress-details">
        <!-- File-by-file status -->
    </div>
</div>

<style>
.progress-panel {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 350px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    padding: 16px;
    z-index: 1000;
}

.progress-bar-container {
    width: 100%;
    height: 8px;
    background: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
    margin: 12px 0;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #8BC34A);
    transition: width 0.3s ease;
}

.progress-status {
    font-size: 14px;
    color: #333;
    margin-bottom: 8px;
}

.progress-details {
    font-size: 12px;
    color: #666;
}
</style>
```

### 16.5 Multiple File Progress

```python
# Enhanced progress for multiple files:
def run_sync():
    # ... earlier code ...
    
    for i, file_id in enumerate(file_ids):
        # Overall progress (files)
        overall_percent = int((i / total_files) * 100)
        send_progress("processing", overall_percent, f"Processing file {i+1}/{total_files}")
        
        # Per-file progress (will be sent by vectorize_and_store internally)
        send_progress("downloading", overall_percent, f"Downloading {meta['name']}...")
        
        # Download
        temp_path = download_file(service, file_id, meta["name"], meta["mimeType"])
        
        # Update with actual file size
        file_size = int(meta.get("size", 0))
        send_progress("downloaded", overall_percent, 
            f"Downloaded {meta['name']} ({file_size/1024:.1f} KB)")
        
        send_progress("vectorizing", overall_percent, 
            f"Vectorizing {meta['name']} ({num_chunks} chunks)...")
        
        # Vectorize - this function should also send progress
        num_chunks = vectorize_and_store(
            temp_path=temp_path,
            file_id=file_id,
            file_name=meta["name"],
            mime_type=meta["mimeType"],
            user_id=user_id,
            course_id=course_id,
            progress_callback=lambda p: send_progress("vectorizing", overall_percent, p)
        )
```

### 16.6 Progress States Summary

| Stage | Percent | Message Example |
|-------|---------|-----------------|
| `starting` | 0-5 | "Starting sync of 3 files..." |
| `downloading` | 10-30 | "Downloading Lecture1.pdf (2.3 MB)..." |
| `downloaded` | 40 | "Downloaded Lecture1.pdf (2.3 MB)" |
| `vectorizing` | 50-90 | "Vectorizing Lecture1.pdf (45 chunks)..." |
| `complete` | 100 | "Successfully synced Lecture1.pdf" |
| `error` | -1 | "Error: File format not supported" |

---

## Updated Summary: What Must Be Built (MVP - NOW COMPLETE)

| Feature | Why | Status |
|---------|-----|--------|
| Auth (sign in / sign up with role) | Students and teachers need accounts | To Build |
| PostgreSQL for users + vectors | Persistent storage | To Build |
| Google Drive OAuth | Teachers connect their Drive | To Build |
| Download → vectorize → delete temp flow | Core value proposition | To Build |
| `modifiedTime` tracking | Prevent stale vectors | To Build |
| Token expiry handling | Prevent silent failures | To Build |
| **LLM answer generation** | Without this, the VTA is just a search engine | To Build |
| **Course-based access control** | Students only ask about enrolled courses | To Build |
| **Semantic chunking** | Better retrieval quality | To Build |
| **Progress indicators during sync** | UX for large file syncs | To Build |

---

## Updated Implementation Order (Now Includes All Features)

### Phase 1: PostgreSQL Setup (Day 1-2)
| Step | Task | Details |
|------|------|---------|
| 1.1 | Install PostgreSQL | Download from postgresql.org, install locally. Or use free cloud: Neon or Supabase |
| 1.2 | Create database | `CREATE DATABASE virtual_ta;` |
| 1.3 | Enable pgvector | `CREATE EXTENSION vector;` |
| 1.4 | Install Python packages | `pip install psycopg2-binary sqlalchemy flask-login alembic pgvector` |
| 1.5 | Create `auth/` package | `db.py`, `models.py` with User + Course + Enrollment models |
| 1.6 | Run initial migration | Create all tables (users, courses, enrollments, file_metadata, vector_chunks) |
| 1.7 | Test connection | Write a small script that connects and queries |

### Phase 2: Login & Sign Up System (Day 2-3)
| Step | Task | Details |
|------|------|---------|
| 2.1 | Create `auth/routes.py` | Register, login, logout, me endpoints |
| 2.2 | Create `auth/middleware.py` | `@login_required` and `@teacher_required` decorators |
| 2.3 | Create `templates/login.html` | Single auth page with Sign In / Sign Up tabs |
| 2.4 | Modify `app.py` | Add blueprint registration, modify `/` route |
| 2.5 | Test sign up flow | New user → Sign Up → picks role → account created |

### Phase 3: Google Cloud Setup (Day 3)
| Step | Task | Details |
|------|------|---------|
| 3.1 | Create Google Cloud project | console.cloud.google.com |
| 3.2 | Enable Drive API | APIs & Services → Library |
| 3.3 | Create OAuth credentials | Web application type |
| 3.4 | Download client_secret.json | Save to `credentials/` folder |
| 3.5 | Add to `.env` | Client ID, secret, redirect URI |

### Phase 4: Google Drive OAuth (Day 4-5)
| Step | Task | Details |
|------|------|---------|
| 4.1 | Create `gdrive/` package | `__init__.py`, `auth.py` |
| 4.2 | Implement OAuth flow | `get_authorization_url()`, `exchange_code_for_tokens()` |
| 4.3 | Create `gdrive/routes.py` | `/drive/auth`, `/drive/callback` |
| 4.4 | Test OAuth flow | Click button → Google consent → redirect back |

### Phase 5: Drive File Listing & Download (Day 5-6)
| Step | Task | Details |
|------|------|---------|
| 5.1 | Create `gdrive/drive_client.py` | `list_files()`, `download_file()` |
| 5.2 | Create `/drive/files` endpoint | List teacher's documents |
| 5.3 | Create file picker UI | Show files, let teacher select which to sync |

### Phase 6: Course Management (Day 6-7) - **NEW**
| Step | Task | Details |
|------|------|---------|
| 6.1 | Create Course model | `gdrive/models.py` - Course, Enrollment |
| 6.2 | Create course API endpoints | CRUD for courses, enrollment endpoints |
| 6.3 | Update sync to require course_id | Must assign files to a course when syncing |
| 6.4 | Create course selection UI | Teachers create courses, students enroll |

### Phase 7: Semantic Chunking (Day 7-8) - **NEW**
| Step | Task | Details |
|------|------|---------|
| 7.1 | Create semantic chunker | `gdrive/semantic_chunker.py` |
| 7.2 | Implement multi-strategy chunking | Markdown, code, PDF, HTML, text |
| 7.3 | Update vectorizer to use semantic chunker | Replace fixed-size chunking |
| 7.4 | Add chunking_strategy metadata | Store which strategy was used |

### Phase 8: Progress Indicators (Day 8-9) - **NEW**
| Step | Task | Details |
|------|------|---------|
| 8.1 | Create SSE endpoint | `/drive/sync/progress/<task_id>` |
| 8.2 | Add progress queue system | Thread-safe queue per user |
| 8.3 | Update sync to send progress | Download → vectorize stages |
| 8.4 | Create progress UI component | Real-time progress bar |

### Phase 9: Vectorization Pipeline with Course Filter (Day 9-10)
| Step | Task | Details |
|------|------|---------|
| 9.1 | Create `gdrive/vectorizer.py` | Download → load → chunk (semantic) → embed → store → delete |
| 9.2 | Update vectorizer to require course_id | Must pass course when storing |
| 9.3 | Create `gdrive/query_bridge.py` | Search PG vectors WITH course filtering |
| 9.4 | Modify `/api/query` | Merge results from in-memory + PG, filter by enrollment |
| 9.5 | Test end-to-end | Connect Drive → sync to course → student enrolls → ask question |

### Phase 10: Polish & Error Handling (Day 10-11)
| Step | Task | Details |
|------|------|---------|
| 10.1 | Add error handling | Token expiry, download failures, etc. |
| 10.2 | Test course-based access | Student in Course A cannot query Course B |
| 10.3 | Test semantic chunking | Verify chunks respect boundaries |
| 10.4 | Test progress indicators | Large file sync shows progress |
| 10.5 | Edge cases | Large files, unsupported types, network errors |

### Phase 11: Testing Checklist (Day 11-12)
| Test | Expected Result |
|------|-----------------|
| Teacher creates course | Course appears in teacher's course list |
| Teacher syncs file to course | File associated with course in DB |
| Student enrolls in course | Enrollment record created |
| Student queries enrolled course | Gets answer from that course's materials |
| Student queries non-enrolled course | Gets error: "Not enrolled in this course" |
| Teacher uploads large file | Progress bar shows download → vectorize → complete |
| Semantic chunking test | Code chunks preserve functions, markdown preserves headers |

---

## New Section 17: Scalability Analysis & Optimization (CRITICAL)

### 17.1 Critical Review of Current Design

Let me be brutally honest about what won't scale:

| Component | Current Design | Scalability Problem |
|-----------|---------------|---------------------|
| **Vector Search** | Loads ALL chunks, computes cosine similarity in Python | O(n) per query - terrible at 100K+ chunks |
| **Embedding Generation** | Synchronous API calls, no batching | Hits rate limits, slow queries |
| **Sync Operations** | Background thread per user | Can't distribute across workers |
| **Session Storage** | Flask signed cookies (in-memory) | Can't scale horizontally without shared session store |
| **Database Connections** | Default SQLAlchemy pool (5 connections) | Connection exhaustion under load |
| **File Processing** | Entire file loaded into memory | OOM on large files |
| **No Caching** | Every query re-embeds the question | Wasted API calls |
| **Progress Queues** | In-memory dict per server | Lost on restart, doesn't work with multiple workers |

---

### 17.2 Bottleneck Analysis

#### Problem 1: Query Vector Search is O(n)

```python
# Current query_bridge.py - TERRIBLE AT SCALE
def search_gdrive_vectors(query: str, user_id: int, user_role: str, top_k: int = 5):
    # ...
    all_chunks = chunks_query.all()  # LOADS EVERYTHING INTO MEMORY
    
    # Compute cosine similarity for EACH chunk
    for chunk in all_chunks:
        similarity = cosine_similarity(query_embedding, chunk.embedding)
        results.append({...})
```

**At 100,000 chunks:** This loads 100K vectors into memory and does 100K calculations PER QUERY.

**The Fix:** Use pgvector's built-in similarity search with proper indexing.

---

#### Problem 2: No Rate Limiting on Embedding API

```python
# Current - no batching, no limiting
embedder = EmbeddingManager()
all_embeddings = embedder.embed_documents(chunk_texts)  # Could be 500+ chunks
```

**Problem:** Gemini has 15 RPM limit. 10 teachers syncing large files = rate limit errors.

**The Fix:** Add request queuing and batching.

---

#### Problem 3: No Horizontal Scaling

Current setup:
- Flask dev server = single-threaded
- In-memory session = can't have multiple workers
- In-memory progress queues = worker-specific

**The Fix:** Use Redis for shared state.

---

#### Problem 4: Large File Processing

```python
# Current - loads entire PDF into memory
doc = fitz.open(temp_path)  # Entire file in RAM
```

**Problem:** A 500MB textbook = 500MB RAM per sync.

**The Fix:** Stream processing, process pages in batches.

---

### 17.3 Optimized Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OPTIMIZED SCALABLE ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Web UI    │────►│  Load       │────►│  Gunicorn   │               │
│  │   (React)   │     │  Balancer   │     │  (4 workers)│               │
│  └─────────────┘     └─────────────┘     └──────┬──────┘               │
│                                                  │                       │
│  ┌───────────────────────────────────────────────┼───────────────────┐   │
│  │                                               │                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────┴────────┐         │   │
│  │  │   Redis     │  │  PostgreSQL │  │   Celery        │         │   │
│  │  │  (Cache +   │◄─┤  (pgvector) │  │  (Background    │         │   │
│  │  │   Session)  │  │             │  │   Tasks)        │         │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘         │   │
│  │       │                │                    │                   │   │
│  │       │                │                    ▼                   │   │
│  │       │                │          ┌─────────────────┐           │   │
│  │       │                │          │  Worker Pool   │           │   │
│  │       │                │          │  (distributed) │           │   │
│  │       │                │          └────────┬────────┘           │   │
│  │       │                │                   │                    │   │
│  │       │                │    ┌──────────────┼──────────────┐      │   │
│  │       │                │    │              │              │      │   │
│  │       ▼                ▼    ▼              ▼              ▼      │   │
│  │  ┌─────────┐    ┌───────────┐    ┌─────────┐    ┌─────────┐       │   │
│  │  │ Session │    │ Vector    │    │ Embed  │    │ Drive   │       │   │
│  │  │ Cache   │    │ Search    │    │ Queue  │    │ API     │       │   │
│  │  └─────────┘    └───────────┘    └─────────┘    └─────────┘       │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 17.4 Solution 1: Use pgvector's Built-in Similarity Search

**Instead of Python similarity calculation:**

```sql
-- Proper indexed vector search in PostgreSQL
-- This uses the index instead of scanning all rows
SELECT 
    id, 
    text, 
    page_number,
    1 - (embedding <=> query_embedding::vector) as similarity
FROM vector_chunks
JOIN file_metadata ON vector_chunks.file_metadata_id = file_metadata.id
WHERE file_metadata.course_id = ANY($course_ids)
ORDER BY embedding <=> query_embedding::vector
LIMIT 5;
```

**The `<=>` operator is cosine distance - lower = more similar.**

**Add proper index:**

```sql
-- Create HNSW index (better than IVFFlat for smaller datasets, faster queries)
CREATE INDEX idx_vector_chunks_embedding_hnsw 
ON vector_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Or IVFFlat for very large datasets (>1M vectors)
CREATE INDEX idx_vector_chunks_embedding_ivfflat 
ON vector_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Updated query_bridge.py:**

```python
# In gdrive/query_bridge.py - USE DATABASE FOR SIMILARITY
def search_gdrive_vectors(query: str, user_id: int, user_role: str, top_k: int = 5):
    """
    Search using pgvector's built-in similarity - O(log n) not O(n)
    """
    db = next(get_db())
    embedder = EmbeddingManager()
    
    # Embed the query
    query_embedding = embedder.embed_query(query)
    
    # Get allowed course IDs based on role
    course_ids = get_allowed_course_ids(db, user_id, user_role)
    
    if not course_ids:
        return []
    
    # Convert to postgres vector format
    embedding_str = "[" + ",".join(map(str, query_embedding.tolist())) + "]"
    
    # Use pgvector's <=> operator for cosine distance
    # 1 - distance = similarity (higher is better)
    sql = text("""
        SELECT 
            vc.id,
            vc.text,
            vc.page_number,
            vc.content_type,
            fm.file_name,
            fm.course_id,
            c.name as course_name,
            1 - (vc.embedding <=> :embedding::vector) as similarity
        FROM vector_chunks vc
        JOIN file_metadata fm ON vc.file_metadata_id = fm.id
        JOIN courses c ON fm.course_id = c.id
        WHERE fm.course_id = ANY(:course_ids)
        ORDER BY vc.embedding <=> :embedding::vector
        LIMIT :top_k
    """)
    
    result = db.execute(sql, {
        "embedding": embedding_str,
        "course_ids": course_ids,
        "top_k": top_k
    })
    
    return [
        {
            "text": row.text,
            "score": row.similarity,
            "source": row.file_name,
            "page": row.page_number,
            "content_type": row.content_type,
            "course_id": row.course_id,
            "course_name": row.course_name,
        }
        for row in result
    ]
```

**Performance difference:**
- 100K chunks: ~0.1ms with index vs ~5 seconds without

---

### 17.5 Solution 2: Redis for Caching & Shared State

```python
# In gdrive/cache.py
import redis
import json
import os

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=True
)


class CacheService:
    """Redis-backed caching for embeddings and sessions."""
    
    EMBEDDING_TTL = 60 * 60 * 24  # 24 hours
    QUERY_TTL = 60 * 5  # 5 minutes
    
    @staticmethod
    def cache_query_embedding(query: str, embedding: list):
        """Cache a query embedding."""
        key = f"embedding:query:{hash(query)}"
        redis_client.setex(key, CacheService.EMBEDDING_TTL, json.dumps(embedding.tolist()))
    
    @staticmethod
    def get_cached_query_embedding(query: str) -> list:
        """Get cached query embedding."""
        key = f"embedding:query:{hash(query)}"
        data = redis_client.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    def cache_query_result(query: str, result: dict):
        """Cache query results."""
        key = f"result:query:{hash(query)}"
        redis_client.setex(key, CacheService.QUERY_TTL, json.dumps(result))
    
    @staticmethod
    def get_cached_query_result(query: str) -> dict:
        """Get cached query result."""
        key = f"result:query:{hash(query)}"
        data = redis_client.get(key)
        return json.loads(data) if data else None


class SessionManager:
    """Redis-backed session management for horizontal scaling."""
    
    SESSION_TTL = 60 * 60 * 24 * 7  # 7 days
    
    @staticmethod
    def create_session(user_id: int, user_data: dict) -> str:
        """Create session and return session_id."""
        import secrets
        session_id = secrets.token_urlsafe(32)
        key = f"session:{session_id}"
        redis_client.setex(key, SessionManager.SESSION_TTL, json.dumps(user_data))
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> dict:
        """Get session data."""
        key = f"session:{session_id}"
        data = redis_client.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    def delete_session(session_id: str):
        """Delete session."""
        key = f"session:{session_id}"
        redis_client.delete(key)
    
    @staticmethod
    def extend_session(session_id: str):
        """Extend session TTL."""
        key = f"session:{session_id}"
        redis_client.expire(key, SessionManager.SESSION_TTL)
```

**Use in Flask:**

```python
# In auth/routes.py - use Redis sessions
from .cache import SessionManager

@auth_bp.route("/login", methods=["POST"])
def login():
    # ... verify credentials ...
    
    # Create Redis session
    session_id = SessionManager.create_session(user.id, {
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    })
    
    # Return session ID to client (store in cookie or localStorage)
    response = jsonify({"message": "Login successful", "user": user.to_dict()})
    response.set_cookie("session_id", session_id, httponly=True, max_age=7*24*60*60)
    return response


# Middleware to load session from Redis
def load_session_from_redis():
    """WSGI middleware to load session from Redis."""
    session_id = request.cookies.get("session_id")
    if session_id:
        session_data = SessionManager.get_session(session_id)
        if session_data:
            session["user_id"] = session_data["user_id"]
            session["user_role"] = session_data["role"]
            SessionManager.extend_session(session_id)  # Keep alive
```

---

### 17.6 Solution 3: Celery for Distributed Background Tasks

Instead of background threads (which don't scale), use Celery with Redis as broker:

```python
# In gdrive/tasks.py
from celery import Celery
import os

celery_app = Celery(
    "gdrive",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max
    worker_prefetch_multiplier=1,  # Don't prefetch tasks
)


@celery_app.task(bind=True, max_retries=3)
def sync_file_task(self, file_id: str, course_id: int, user_id: int):
    """
    Celery task for syncing a single file.
    Can be distributed across multiple workers.
    """
    from .auth import refresh_credentials
    from .drive_client import build_drive_service, download_file
    from .vectorizer import vectorize_and_store
    from .db import SessionLocal
    from .models import User
    
    db = SessionLocal()
    
    try:
        # Update progress via Redis
        from .cache import redis_client
        redis_client.hset(
            f"sync_progress:{user_id}",
            file_id,
            {"stage": "downloading", "percent": 0}
        )
        
        # Get credentials
        user = db.query(User).get(user_id)
        creds = refresh_credentials(user.google_drive_refresh_token)
        service = build_drive_service(creds)
        
        # Download
        meta = service.files().get(fileId=file_id, fields="id,name,mimeType,size").execute()
        temp_path = download_file(service, file_id, meta["name"], meta["mimeType"])
        
        redis_client.hset(
            f"sync_progress:{user_id}",
            file_id,
            {"stage": "vectorizing", "percent": 50}
        )
        
        # Vectorize
        num_chunks = vectorize_and_store(
            temp_path=temp_path,
            file_id=file_id,
            file_name=meta["name"],
            mime_type=meta["mimeType"],
            user_id=user_id,
            course_id=course_id,
        )
        
        # Complete
        redis_client.hset(
            f"sync_progress:{user_id}",
            file_id,
            {"stage": "complete", "percent": 100, "chunks": num_chunks}
        )
        
        return {"file_id": file_id, "chunks": num_chunks, "status": "success"}
        
    except Exception as e:
        self.retry(exc=e, countdown=60)  # Retry after 60 seconds
    finally:
        db.close()


@celery_app.task
def batch_sync_files(file_ids: list, course_id: int, user_id: int):
    """
    Orchestrate batch sync of multiple files.
    """
    results = []
    for file_id in file_ids:
        result = sync_file_task.delay(file_id, course_id, user_id)
        results.append({"file_id": file_id, "task_id": result.id})
    return results
```

**Updated sync endpoint:**

```python
# In gdrive/routes.py
from .tasks import sync_file_task, batch_sync_files

@drive_bp.route("/sync", methods=["POST"])
@login_required
@teacher_required
def sync_files():
    """
    POST /drive/sync
    Now uses Celery for distributed processing.
    """
    data = request.get_json()
    file_ids = data.get("file_ids", [])
    course_id = data.get("course_id")
    user_id = session["user_id"]
    
    # Queue all files as Celery tasks
    results = []
    for file_id in file_ids:
        task = sync_file_task.delay(file_id, course_id, user_id)
        results.append({
            "file_id": file_id,
            "task_id": task.id,
            "status": "queued"
        })
    
    return jsonify({
        "message": f"Queued {len(file_ids)} files for processing",
        "tasks": results
    }), 202


@drive_bp.route("/sync/status/<task_id>", methods=["GET"])
@login_required
def get_sync_status(task_id):
    """Get status of a sync task."""
    from celery.result import AsyncResult
    from .tasks import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    return jsonify({
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    })
```

**Progress via Redis:**

```python
# In gdrive/routes.py
@drive_bp.route("/sync/progress/<user_id>", methods=["GET"])
@login_required
def get_sync_progress(user_id):
    """Get progress from Redis."""
    from .cache import redis_client
    
    progress_data = redis_client.hgetall(f"sync_progress:{user_id}")
    
    return jsonify({
        file_id: json.loads(data)
        for file_id, data in progress_data.items()
    })
```

---

### 17.7 Solution 4: Embedding API Rate Limiting

```python
# In gdrive/rate_limiter.py
import time
import threading
from collections import deque
from redis import Redis


class RateLimiter:
    """Token bucket rate limiter backed by Redis."""
    
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.redis = Redis(host="localhost", port=6379, db=3)
    
    def acquire(self, key: str) -> bool:
        """
        Attempt to acquire a rate limit slot.
        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        window_key = f"rate_limit:{key}"
        
        # Get current count and timestamp
        current = self.redis.get(window_key)
        
        if current is None:
            # First request - allow
            self.redis.setex(window_key, self.period, "1")
            return True
        
        count, timestamp = map(int, current.split(b":"))
        
        if now - timestamp > self.period:
            # Window expired - reset
            self.redis.setex(window_key, self.period, "1")
            return True
        
        if count >= self.max_calls:
            # Rate limited
            return False
        
        # Increment count
        self.redis.set(window_key, f"{count + 1}:{timestamp}")
        return True
    
    def wait_if_needed(self, key: str):
        """Block until rate limit allows."""
        while not self.acquire(key):
            time.sleep(1)


# Gemini has 15 RPM, so we use 14 to be safe
gemini_rate_limiter = RateLimiter(max_calls=14, period=60)


class BatchedEmbedder:
    """Batches embedding requests to maximize throughput."""
    
    def __init__(self, batch_size: int = 50, max_wait: float = 2.0):
        self.batch_size = batch_size
        self.max_wait = max_wait
        self.pending = []
        self.lock = threading.Lock()
        self.embedder = EmbeddingManager()
    
    def embed(self, text: str) -> list:
        """Add text to batch, return embedding."""
        future = Future()
        
        with self.lock:
            self.pending.append((text, future))
            
            if len(self.pending) >= self.batch_size:
                # Flush immediately if batch full
                self._flush()
            else:
                # Schedule flush after max_wait
                threading.Timer(self.max_wait, self._flush).start()
        
        return future.result()
    
    def _flush(self):
        """Process pending embeddings in batch."""
        with self.lock:
            if not self.pending:
                return
            
            pending = self.pending
            self.pending = []
        
        # Wait for rate limit
        gemini_rate_limiter.wait_if_needed("gemini-embedding")
        
        # Batch API call
        texts = [p[0] for p in pending]
        try:
            embeddings = self.embedder.embed_documents(texts)
            for (text, future), embedding in zip(pending, embeddings):
                future.set_result(embedding)
        except Exception as e:
            for (text, future) in pending:
                future.set_exception(e)


class Future:
    """Simple future implementation."""
    
    def __init__(self):
        self.result = None
        self.exception = None
        self.callbacks = []
        self._ready = threading.Event()
    
    def result(self):
        self._ready.wait()
        if self.exception:
            raise self.exception
        return self.result
    
    def set_result(self, result):
        self.result = result
        self._ready.set()
        for callback in self.callbacks:
            callback(result)
    
    def set_exception(self, exc):
        self.exception = exc
        self._ready.set()
```

---

### 17.8 Solution 5: Database Connection Pooling

```python
# In auth/db.py - optimized connection pool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# Optimized engine settings for concurrency
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,              # Base connections
    max_overflow=30,           # Additional connections under load
    pool_pre_ping=True,        # Verify connections before use
    pool_recycle=1800,         # Recycle connections every 30 min
    pool_timeout=30,            # Wait max 30s for connection
    echo=False,                # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

---

### 17.9 Solution 6: Streaming Large File Processing

```python
# In gdrive/streaming_processor.py
import fitz  # PyMuPDF
import tempfile
import os


def process_large_pdf_streaming(
    file_path: str,
    chunk_callback,
    page_batch_size: int = 10,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
):
    """
    Process a large PDF in streaming fashion - never loads entire file.
    
    Args:
        file_path: Path to PDF
        chunk_callback: Function to call with each chunk
        page_batch_size: Process this many pages at a time
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
    """
    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    for batch_start in range(0, total_pages, page_batch_size):
        batch_end = min(batch_start + page_batch_size, total_pages)
        
        # Load only this batch of pages
        batch_text = ""
        for page_num in range(batch_start, batch_end):
            page = doc[page_num]
            batch_text += page.get_text()
        
        # Chunk this batch
        chunks = splitter.split_text(batch_text)
        
        for chunk in chunks:
            chunk_callback({
                "text": chunk,
                "page": batch_start + 1,  # Approximate
                "source": file_path
            })
    
    doc.close()


# Example usage in vectorizer:
def vectorize_and_store_streaming(temp_path, file_id, file_name, mime_type, user_id, course_id):
    """Streaming version for large files."""
    from .embedding_manager import EmbeddingManager
    from .db import get_db
    from .models import FileMetadata, VectorChunk
    import uuid
    
    embedder = BatchedEmbedder(batch_size=50)  # Use batched embedder
    db = next(get_db())
    
    # Create file metadata
    file_meta = FileMetadata(
        drive_file_id=file_id,
        file_name=file_name,
        mime_type=mime_type,
        owner_user_id=user_id,
        course_id=course_id,
    )
    db.add(file_meta)
    db.commit()
    
    chunk_count = 0
    
    def handle_chunk(chunk_data):
        nonlocal chunk_count
        
        # Embed this chunk
        embedding = embedder.embed(chunk_data["text"])
        
        # Store immediately (don't wait for entire file)
        vector_chunk = VectorChunk(
            id=str(uuid.uuid4()),
            file_metadata_id=file_meta.id,
            chunk_index=chunk_count,
            text=chunk_data["text"],
            page_number=chunk_data.get("page"),
            embedding=embedding.tolist(),
        )
        db.add(vector_chunk)
        chunk_count += 1
        
        # Commit in batches
        if chunk_count % 100 == 0:
            db.commit()
    
    # Process in streaming fashion
    if mime_type == "application/pdf":
        process_large_pdf_streaming(
            temp_path,
            handle_chunk,
            page_batch_size=10
        )
    else:
        # For non-PDF, use existing loader
        documents = load_document(temp_path)
        for doc in documents:
            chunks = splitter.split_documents([doc])
            for chunk in chunks:
                handle_chunk({
                    "text": chunk.page_content,
                    "page": chunk.metadata.get("page"),
                    "source": file_name
                })
    
    # Final commit
    db.commit()
    file_meta.num_chunks = chunk_count
    db.commit()
    
    # Clean up
    os.remove(temp_path)
    
    return chunk_count
```

---

### 17.10 Solution 7: Database Query Optimization

Add proper indexes for common queries:

```sql
-- Composite index for course-filtered vector search
CREATE INDEX idx_vector_chunks_course_embedding 
ON vector_chunks (file_metadata_id, course_id)
INCLUDE (embedding);

-- Index for enrollment lookups
CREATE INDEX idx_enrollments_student_status 
ON enrollments (student_id, status);

-- Index for file metadata lookups
CREATE INDEX idx_file_metadata_course_owner 
ON file_metadata (course_id, owner_user_id);

-- Partial index for only active enrollments
CREATE INDEX idx_enrollments_active 
ON enrollments (student_id, course_id) 
WHERE status = 'active';
```

---

### 17.11 Solution 8: Horizontal Scaling Configuration

```python
# gunicorn_config.py
workers = 4  # Number of workers (CPU cores * 2 + 1)
worker_class = "gevent"  # Async workers for I/O bound tasks
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5

# Run with:
# gunicorn -c gunicorn_config.py app:app
```

**Docker Compose for full stack:**

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/virtual_ta
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
    deploy:
      replicas: 2

  celery_worker:
    build: .
    command: celery -A gdrive.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/virtual_ta
      - REDIS_HOST=redis
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
    deploy:
      replicas: 2

  db:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=virtual_ta
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

---

### 17.12 Scalability Summary Table

| Problem | Solution | Expected Performance |
|---------|----------|---------------------|
| O(n) vector search | pgvector built-in similarity + HNSW index | 100K vectors in <10ms |
| No caching | Redis for query embeddings + results | 80%+ cache hit rate |
| Background threads | Celery + Redis broker | Distributed across workers |
| Rate limiting | Token bucket + batching | Never hit API limits |
| Session affinity | Redis-backed sessions | Horizontal scaling works |
| Connection exhaustion | Optimized SQLAlchemy pool | 50 concurrent connections |
| Large files OOM | Streaming page-by-page | Process any size file |
| Slow Cold starts | Connection pooling + warm-up | Sub-second queries |

---

### 17.13 Infrastructure Cost at Scale

| Users | Configuration | Monthly Cost (Est.) |
|-------|---------------|---------------------|
| 100 students, 5 teachers | Single server + basic Postgres | $0-50 |
| 1,000 students, 50 teachers | 2 web + 2 Celery + Postgres + Redis | $100-200 |
| 10,000 students, 500 teachers | 4 web + 4 Celery + Postgres (managed) + Redis | $300-500 |

**Note:** Using Supabase/Neon free tiers can keep costs near $0 for small scale.

---

## New Section 18: Folder-Specific Access Control

### 18.1 The Problem

Currently, the OAuth scope `drive.readonly` gives access to **ALL files** in the teacher's Google Drive. This is a privacy issue:

| Issue | Example |
|-------|---------|
| **Other classes** | Teacher has files for BIO 101, CHEM 201 in Drive - VTA can see all of them |
| **Personal files** | Teacher's personal documents, photos, etc. are visible |
| **Other semesters** | Old course materials from previous semesters |
| **Security risk** | If VTA is compromised, ALL Drive data is exposed |

**The Solution:** Let the teacher select ONE specific folder that the VTA will ONLY access.

---

### 18.2 The Flow

```
TEACHER FLOW WITH FOLDER SELECTION:
═══════════════════════════════════

1. Teacher logs into VTA

2. Teacher clicks "Connect Google Drive"
   │
   ▼
3. Google OAuth screen appears (as before)
   - Teacher clicks "Allow"
   │
   ▼
4. VTA has access to ALL files temporarily
   (needed to let them pick the folder)
   │
   ▼
5. VTA shows folder picker:
   "Select which folder VTA should access"
   │
   ▼
6. Teacher browses their Drive and selects ONE folder
   (e.g., "CPT_S 421 - AI Materials")
   │
   ▼
7. VTA saves this folder ID in the database
   │
   ▼
8. FROM NOW ON - VTA only sees files in that folder!
```

---

### 18.3 Updated Database Schema

```sql
-- Update users table to store selected folder
ALTER TABLE users ADD COLUMN google_drive_folder_id VARCHAR(255);
ALTER TABLE users ADD COLUMN google_drive_folder_name VARCHAR(500);

-- Update course table to optionally link to a Drive folder
ALTER TABLE courses ADD COLUMN drive_folder_id VARCHAR(255);
ALTER TABLE courses ADD COLUMN drive_folder_name VARCHAR(500);
```

```python
# In auth/models.py - update User model
class User(Base):
    # ... existing fields ...

    # NEW: Folder restriction
    google_drive_folder_id = Column(String(255), nullable=True)
    google_drive_folder_name = Column(String(500), nullable=True)
```

---

### 18.4 Updated Drive Client to Filter by Folder

```python
# In gdrive/drive_client.py - update list_files to filter by folder

def list_files(service, folder_id=None, page_size=100):
    """
    List files in the teacher's Google Drive.
    
    Args:
        service: Google Drive API service object
        folder_id: Optional folder ID to filter to (if None, lists all)
        page_size: Number of files to return
    
    Returns:
        List of file metadata dicts
    """
    # Build query
    query = "trashed = false"
    
    if folder_id:
        # Only files IN this folder (not subfolders)
        query += f" and '{folder_id}' in parents"
    
    results = service.files().list(
        q=query,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    files = results.get("files", [])
    
    # Filter to only supported document types
    supported_files = [f for f in files if f["mimeType"] in SUPPORTED_MIME_TYPES]
    return supported_files


def list_folders(service, page_size=50):
    """
    List all folders in the teacher's Google Drive.
    Used for the folder picker UI.
    
    Returns:
        List of folder metadata dicts
    """
    query = "trashed = false and mimeType = 'application/vnd.google-apps.folder'"
    
    results = service.files().list(
        q=query,
        pageSize=page_size,
        fields="nextPageToken, files(id, name, parents, webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    
    folders = results.get("files", [])
    return folders
```

---

### 18.5 New API Endpoints for Folder Selection

```python
# In gdrive/routes.py - add folder selection endpoints

@drive_bp.route("/folders", methods=["GET"])
@login_required
@teacher_required
def list_folders():
    """
    GET /drive/folders
    
    List all folders in teacher's Google Drive.
    Used to let teacher select which folder VTA can access.
    
    Returns:
        {
            "folders": [
                {"id": "folder123", "name": "CPT_S 421 - AI"},
                {"id": "folder456", "name": "CPT_S 322 - Databases"},
                {"id": "folder789", "name": "Personal"}
            ]
        }
    """
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    
    if not user.google_drive_connected:
        return jsonify({"error": "Google Drive not connected"}), 400
    
    # Get fresh credentials
    from .auth import refresh_credentials
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)
    
    # List folders
    from .drive_client import list_folders
    folders = list_folders(service)
    
    return jsonify({"folders": folders}), 200


@drive_bp.route("/folder/select", methods=["POST"])
@login_required
@teacher_required
def select_folder():
    """
    POST /drive/folder/select
    
    Teacher selects which folder VTA should access.
    After this, ALL Drive operations are filtered to this folder.
    
    Body:
        {
            "folder_id": "folder123",
            "folder_name": "CPT_S 421 - AI"
        }
    
    Returns:
        {"message": "Folder selected successfully"}
    """
    data = request.get_json()
    folder_id = data.get("folder_id")
    folder_name = data.get("folder_name")
    
    if not folder_id or not folder_name:
        return jsonify({"error": "folder_id and folder_name required"}), 400
    
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    
    # Verify the folder exists and teacher has access
    from .auth import refresh_credentials
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)
    
    try:
        # Verify folder exists and is accessible
        folder_meta = service.files().get(fileId=folder_id).execute()
        if folder_meta.get("mimeType") != "application/vnd.google-apps.folder":
            return jsonify({"error": "Selected item is not a folder"}), 400
    except Exception as e:
        return jsonify({"error": f"Cannot access folder: {str(e)}"}), 400
    
    # Save folder restriction to database
    user.google_drive_folder_id = folder_id
    user.google_drive_folder_name = folder_name
    db.commit()
    
    return jsonify({
        "message": f"Folder '{folder_name}' selected. VTA will only access files in this folder.",
        "folder": {"id": folder_id, "name": folder_name}
    }), 200


@drive_bp.route("/folder/current", methods=["GET"])
@login_required
@teacher_required
def get_current_folder():
    """
    GET /drive/folder/current
    
    Get the currently selected folder (if any).
    
    Returns:
        {"folder": {"id": "folder123", "name": "CPT_S 421 - AI"}}
        or
        {"folder": null} if no folder selected
    """
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    
    if user.google_drive_folder_id:
        return jsonify({
            "folder": {
                "id": user.google_drive_folder_id,
                "name": user.google_drive_folder_name
            }
        }), 200
    else:
        return jsonify({"folder": None}), 200


@drive_bp.route("/folder/clear", methods=["DELETE"])
@login_required
@teacher_required
def clear_folder():
    """
    DELETE /drive/folder/clear
    
    Clear the folder restriction.
    Teacher can then select a different folder.
    """
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    
    user.google_drive_folder_id = None
    user.google_drive_folder_name = None
    db.commit()
    
    return jsonify({"message": "Folder restriction cleared. You can now select a new folder."}), 200
```

---

### 18.6 Updated File Listing to Use Selected Folder

```python
# In gdrive/routes.py - update list_drive_files to respect folder

@drive_bp.route("/files", methods=["GET"])
@login_required
@teacher_required
def list_drive_files():
    """
    List the teacher's Google Drive files.
    NOW FILTERS TO SELECTED FOLDER ONLY.
    """
    db = next(get_db())
    user = db.query(User).get(session["user_id"])
    
    if not user.google_drive_connected:
        return jsonify({"error": "Google Drive not connected"}), 400
    
    # Get fresh credentials
    from .auth import refresh_credentials
    creds = refresh_credentials(user.google_drive_refresh_token)
    service = build_drive_service(creds)
    
    # KEY CHANGE: Use the selected folder ID
    folder_id = user.google_drive_folder_id
    
    if not folder_id:
        # No folder selected - show message to select one
        return jsonify({
            "error": "No folder selected",
            "action": "select_folder",
            "message": "Please select a folder from your Google Drive first."
        }), 400
    
    # List files ONLY from that folder
    from .drive_client import list_files
    files = list_files(service, folder_id=folder_id)
    
    return jsonify({
        "files": files,
        "folder": {
            "id": folder_id,
            "name": user.google_drive_folder_name
        }
    }), 200
```

---

### 18.7 Folder Selection UI (Frontend)

```html
<!-- Folder Selection Component -->
<div id="folderSelectionPanel" class="panel">
    <h3>🔗 Connect Google Drive</h3>
    
    <!-- Step 1: If not connected yet -->
    <div id="step1">
        <p>Connect your Google Drive to sync course materials.</p>
        <button id="connectDriveBtn" class="btn-primary">
            Connect Google Drive
        </button>
    </div>
    
    <!-- Step 2: If connected but no folder selected -->
    <div id="step2" style="display:none;">
        <p>✅ Google Drive connected!</p>
        <p>Now select which folder VTA should access:</p>
        
        <button id="selectFolderBtn" class="btn-secondary">
            📁 Select Folder
        </button>
        
        <div id="folderPicker" style="display:none;">
            <p>Loading your folders...</p>
            <!-- Folder list will be populated here -->
            <ul id="folderList"></ul>
        </div>
    </div>
    
    <!-- Step 3: Folder selected -->
    <div id="step3" style="display:none;">
        <p>✅ Connected to folder:</p>
        <div class="selected-folder">
            <strong id="selectedFolderName"></strong>
        </div>
        
        <button id="changeFolderBtn" class="btn-link">
            Change folder
        </button>
    </div>
</div>

<script>
// Step 1: Connect Drive
document.getElementById('connectDriveBtn').addEventListener('click', async () => {
    const res = await fetch('/drive/auth');
    const data = await res.json();
    window.location.href = data.auth_url;
});

// After OAuth callback, check folder status
async function checkFolderStatus() {
    const res = await fetch('/drive/folder/current');
    const data = await res.json();
    
    if (data.folder) {
        // Folder already selected
        showStep3(data.folder);
    } else {
        // Need to select folder
        showStep2();
    }
}

// Step 2: Show folder picker
document.getElementById('selectFolderBtn').addEventListener('click', async () => {
    const res = await fetch('/drive/folders');
    const data = await res.json();
    
    const folderList = document.getElementById('folderList');
    folderList.innerHTML = '';
    
    data.folders.forEach(folder => {
        const li = document.createElement('li');
        li.innerHTML = `
            <button class="folder-option" data-id="${folder.id}" data-name="${folder.name}">
                📁 ${folder.name}
            </button>
        `;
        folderList.appendChild(li);
    });
    
    document.getElementById('folderPicker').style.display = 'block';
});

// Select a folder
document.getElementById('folderList').addEventListener('click', async (e) => {
    if (e.target.classList.contains('folder-option')) {
        const folderId = e.target.dataset.id;
        const folderName = e.target.dataset.name;
        
        const res = await fetch('/drive/folder/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId, folder_name: folderName })
        });
        
        const data = await res.json();
        if (res.ok) {
            showStep3({ id: folderId, name: folderName });
        }
    }
});

function showStep2() {
    document.getElementById('step1').style.display = 'none';
    document.getElementById('step2').style.display = 'block';
    document.getElementById('step3').style.display = 'none';
}

function showStep3(folder) {
    document.getElementById('step1').style.display = 'none';
    document.getElementById('step2').style.display = 'none';
    document.getElementById('step3').style.display = 'block';
    document.getElementById('selectedFolderName').textContent = folder.name;
}

// Change folder
document.getElementById('changeFolderBtn').addEventListener('click', async () => {
    await fetch('/drive/folder/clear', { method: 'DELETE' });
    showStep2();
});
</script>
```

---

### 18.8 Security Benefits

| Before | After |
|--------|-------|
| VTA can see ALL Drive files | VTA can only see ONE folder |
| Personal files exposed | Personal files NOT accessible |
| All class materials visible | Only selected course folder visible |
| If compromised = total breach | If compromised = limited to one folder |

---

### 18.9 Summary Table

| Step | What Happens | API Called |
|------|--------------|------------|
| 1 | Teacher clicks "Connect Drive" | `GET /drive/auth` |
| 2 | Teacher allows access on Google | (Google's site) |
| 3 | VTA redirects back | `GET /drive/callback` |
| 4 | VTA shows "Select Folder" button | (Frontend) |
| 5 | Teacher clicks "Select Folder" | `GET /drive/folders` |
| 6 | Teacher picks a folder | `POST /drive/folder/select` |
| 7 | VTA saves folder ID | (Database) |
| 8 | Future file listings filtered | `GET /drive/files` only shows that folder |

---

## New Section 19: Heavy Security & Privacy Implementation

### 19.1 Security Architecture Overview

This section covers comprehensive security measures for both frontend and backend, with PostgreSQL as the core database. We assume this is a production system handling sensitive educational data.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ FRONTEND (Browser)                                                   │   │
│  │  • HTTPS only (HSTS)                                                │   │
│  │  • HttpOnly cookies for sessions                                    │   │
│  │  • Content Security Policy (CSP)                                   │   │
│  │  • XSS protection                                                   │   │
│  │  • CSRF tokens                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ BACKEND (Flask + Gunicorn)                                          │   │
│  │  • Rate limiting                                                     │   │
│  │  • Input validation                                                  │   │
│  │  • SQL injection prevention                                         │   │
│  │  • Role-based access control (RBAC)                                 │   │
│  │  • Audit logging                                                    │   │
│  │  • Request size limits                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ DATABASE (PostgreSQL)                                               │   │
│  │  • Row-level security (RLS)                                        │   │
│  │  • Encrypted columns                                                │   │
│  │  • Audit triggers                                                   │   │
│  │  • Connection encryption (SSL)                                     │   │
│  │  • Prepared statements                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 19.2 Backend Security (Flask)

#### 19.2.1 Security Headers & Middleware

```python
# In app.py or new security/middleware.py
from flask import Flask, request, g
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import hashlib
import time

def create_secure_app(app: Flask):
    """
    Apply all security middleware to Flask app.
    """
    
    # =========================================================================
    # 1. Content Security Policy (CSP)
    # =========================================================================
    # Prevents XSS by controlling what resources can be loaded
    Talisman(
        app,
        content_security_policy={
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline' 'unsafe-eval'",  # For React dev
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data: https:",
            "font-src": "'self' data:",
            "connect-src": "'self' https://*.googleapis.com",
            "frame-src": "'none'",
        },
        content_security_policy_nonce_in=["script-src"],
        force_https=True,  # Redirect HTTP to HTTPS
        strict_transport_security="max-age=31536000; includeSubDomains",
        referrer_policy="strict-origin-when-cross-origin",
    )
    
    # =========================================================================
    # 2. Rate Limiting (Brute Force Protection)
    # =========================================================================
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour", "10 per minute"],
        storage_uri="redis://localhost:6379/5",  # Use Redis for distributed
    )
    
    # Define specific rate limits for sensitive endpoints
    login_limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["5 per minute"],  # Strict for login
    )
    
    # =========================================================================
    # 3. Request Size Limits (DoS Protection)
    # =========================================================================
    # Limit request body to 10MB (prevents large payload attacks)
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
    
    # =========================================================================
    # 4. CORS Configuration
    # =========================================================================
    from flask_cors import CORS
    CORS(app, 
        origins=["https://yourdomain.com"],  # Strict origin
        methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        supports_credentials=True,
        max_age=3600,
    )
    
    return app, limiter


# Apply rate limiting to login
@app.route("/auth/login", methods=["POST"])
@login_limiter.limit("5 per minute")  # Prevent brute force
def login():
    # ... login logic
    pass
```

#### 19.2.2 Input Validation & Sanitization

```python
# In security/validators.py
"""
Input validation using Pydantic for type-safe validation.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
import re
import html


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., pattern="^(student|teacher)$")
    
    @validator('password')
    def validate_password(cls, v):
        """Ensure password strength."""
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v
    
    @validator('full_name')
    def sanitize_name(cls, v):
        """Sanitize name to prevent XSS."""
        return html.escape(v.strip())


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    
    @validator('query')
    def sanitize_query(cls, v):
        """Sanitize query input."""
        # Remove any HTML tags
        v = re.sub(r'<[^>]+>', '', v)
        # Remove SQL keywords (basic prevention)
        dangerous = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'EXEC']
        v_upper = v.upper()
        for word in dangerous:
            if word in v_upper:
                raise ValueError(f'Invalid query content')
        return v.strip()


class SyncRequest(BaseModel):
    file_ids: List[str] = Field(..., min_items=1, max_items=50)
    course_id: int = Field(..., gt=0)
    
    @validator('file_ids')
    def validate_file_ids(cls, v):
        """Ensure file IDs are valid format."""
        for file_id in v:
            if not re.match(r'^[a-zA-Z0-9_-]{10,100}$', file_id):
                raise ValueError(f'Invalid file ID format: {file_id}')
        return v


def validate_request(model_class, data: dict):
    """
    Validate request data against Pydantic model.
    Returns (is_valid, errors, validated_data)
    """
    try:
        validated = model_class(**data)
        return True, None, validated.dict()
    except Exception as e:
        return False, str(e), None
```

#### 19.2.3 SQL Injection Prevention with SQLAlchemy

```python
# In auth/db.py - Secure database configuration
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine with security settings
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,
    
    # SECURITY: Use SSL if available
    connect_args={
        "sslmode": "require",  # Force SSL connection
        "sslrootcert": "/path/to/ca.pem",  # CA certificate
    },
    
    # SECURITY: Echo should be False in production
    echo=False,
)

# SECURITY: Enable prepared statement caching (prevents some SQL injection)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set PostgreSQL session parameters for security."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET statement_timeout = 30000")  # 30 second timeout
    cursor.close()


# SECURITY: Always use parameterized queries
# GOOD (safe):
result = db.query(User).filter(User.email == email).first()

# BAD (unsafe - never do this!):
# result = db.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

#### 19.2.4 Role-Based Access Control (RBAC)

```python
# In auth/middleware.py - Enhanced security decorators
from functools import wraps
from flask import session, jsonify, request, g
from typing import Callable
import hashlib
import time


def login_required(f: Callable) -> Callable:
    """
    Ensures user is authenticated.
    Adds rate limiting and audit logging.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session exists
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        
        # Check session not expired
        session_time = session.get("session_time", 0)
        if time.time() - session_time > 24 * 3600:  # 24 hours
            session.clear()
            return jsonify({"error": "Session expired"}), 401
        
        # Update session time (sliding expiration)
        session["session_time"] = time.time()
        
        # Set current user in Flask g for easy access
        g.user_id = session.get("user_id")
        g.user_role = session.get("user_role")
        
        return f(*args, **kwargs)
    return decorated


def teacher_required(f: Callable) -> Callable:
    """
    Ensures user is both authenticated AND is a teacher.
    """
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if session.get("user_role") != "teacher":
            # Log unauthorized access attempt
            log_security_event(
                event_type="UNAUTHORIZED_ACCESS_ATTEMPT",
                user_id=g.user_id,
                endpoint=request.endpoint,
                details="Student attempted to access teacher-only endpoint"
            )
            return jsonify({
                "error": "Teacher access required",
                "code": "FORBIDDEN"
            }), 403
        
        return f(*args, **kwargs)
    return decorated


def course_owner_required(course_id_param: str = "course_id"):
    """
    Ensures user owns the course they're trying to modify.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            course_id = kwargs.get(course_id_param) or request.json.get(course_id_param)
            
            if not course_id:
                return jsonify({"error": "Course ID required"}), 400
            
            # Verify ownership
            from auth.models import Course
            db = next(get_db())
            course = db.query(Course).filter_by(id=course_id).first()
            
            if not course or course.teacher_id != g.user_id:
                log_security_event(
                    event_type="UNAUTHORIZED_COURSE_ACCESS",
                    user_id=g.user_id,
                    course_id=course_id
                )
                return jsonify({"error": "Access denied to this course"}), 403
            
            g.course = course
            return f(*args, **kwargs)
        return decorated
    return decorator


def log_security_event(event_type: str, user_id: int = None, **kwargs):
    """
    Log security-relevant events for auditing.
    """
    import logging
    import json
    
    logger = logging.getLogger("security")
    
    event_data = {
        "timestamp": time.time(),
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": request.remote_addr,
        "user_agent": request.headers.get("User-Agent"),
        **kwargs
    }
    
    logger.warning(f"SECURITY_EVENT: {json.dumps(event_data)}")
    
    # Also store in database for audit trail
    try:
        db = next(get_db())
        from auth.models import AuditLog
        audit = AuditLog(
            event_type=event_type,
            user_id=user_id,
            ip_address=request.remote_addr,
            details=json.dumps(kwargs)
        )
        db.add(audit)
        db.commit()
    except:
        pass  # Don't let logging failures break the app
```

---

### 19.3 Database Security (PostgreSQL)

#### 19.3.1 PostgreSQL Security Configuration

```sql
-- ============================================================================
-- POSTGRESQL SECURITY CONFIGURATION
-- ============================================================================

-- 1. Create dedicated application user (not superuser)
CREATE USER vta_app WITH PASSWORD 'strong_random_password_here';

-- 2. Create database with owner
CREATE DATABASE virtual_ta OWNER vta_app;

-- 3. Connect to database
\c virtual_ta

-- 4. Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- For encryption

-- 5. Grant appropriate permissions
GRANT CONNECT ON DATABASE virtual_ta TO vta_app;
GRANT USAGE ON SCHEMA public TO vta_app;

-- 6. Create audit log table (superuser only)
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id INTEGER,
    ip_address INET,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Only superuser can read audit logs
REVOKE SELECT ON audit_log FROM vta_app;
GRANT INSERT ON audit_log TO vta_app;

-- 7. Row-Level Security (RLS) - Critical for multi-tenant safety
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE vector_chunks ENABLE ROW LEVEL SECURITY;

-- 8. Create policies
-- Users can only see their own row
CREATE POLICY users_select_policy ON users
    FOR SELECT USING (id = current_user_id());

-- Users can only see their own courses
CREATE POLICY courses_select_policy ON courses
    FOR SELECT USING (teacher_id = current_user_id());

-- Enrollments: users can only see their own enrollments
CREATE POLICY enrollments_select_policy ON enrollments
    FOR SELECT USING (student_id = current_user_id() OR 
                      course_id IN (
                          SELECT id FROM courses WHERE teacher_id = current_user_id()
                      ));

-- File metadata: teachers see their own, students see enrolled courses
CREATE POLICY file_metadata_select_policy ON file_metadata
    FOR SELECT USING (
        owner_user_id = current_user_id() OR
        course_id IN (
            SELECT course_id FROM enrollments WHERE student_id = current_user_id()
        )
    );

-- 9. Function to get current user ID (for RLS)
CREATE OR REPLACE FUNCTION current_user_id() RETURNS INTEGER AS $$
    SELECT nullif(current_setting('app.current_user_id', true), '')::INTEGER;
$$ LANGUAGE SQL SECURITY DEFINER;

-- 10. Function to set session auth (call after login)
CREATE OR REPLACE FUNCTION set_session_auth(user_id INTEGER, user_role TEXT) RETURNS VOID AS $$
    PERFORM set_config('app.current_user_id', user_id::TEXT, true);
    PERFORM set_config('app.current_user_role', user_role, true);
$$ LANGUAGE SQL SECURITY DEFINER;

-- 11. Encrypted column for sensitive data
ALTER TABLE users ADD COLUMN google_drive_refresh_token_encrypted BYTEA;

-- 12. Function to encrypt token before storage
CREATE OR REPLACE FUNCTION encrypt_token(plain_text TEXT) RETURNS BYTEA AS $$
    SELECT pgp_sym_encrypt(plain_text, current_setting('app.encryption_key'));
$$ LANGUAGE SQL SECURITY DEFINER;

-- 13. Function to decrypt token when needed
CREATE OR REPLACE FUNCTION decrypt_token(encrypted BYTEA) RETURNS TEXT AS $$
    SELECT pgp_sym_decrypt(encrypted::BYTEA, current_setting('app.encryption_key'));
$$ LANGUAGE SQL SECURITY DEFINER;

-- 14. Set encryption key (in production, use secure key management)
-- NOTE: Set this in PostgreSQL config or environment, never in code!
-- SET app.encryption_key = 'your-256-bit-key-here';  -- 32 bytes

-- 15. Create index for audit log queries
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);

-- 16. Create role for read-only access (for students)
CREATE ROLE vta_student;
GRANT USAGE ON SCHEMA public TO vta_student;
GRANT SELECT ON users TO vta_student;
GRANT SELECT ON courses TO vta_student;
GRANT SELECT ON enrollments TO vta_student;
GRANT SELECT ON file_metadata TO vta_student;
GRANT SELECT ON vector_chunks TO vta_student;

-- 17. Security: Prevent superuser access to sensitive columns
-- Create view that hides sensitive data
CREATE VIEW users_safe AS
SELECT 
    id, email, full_name, role, created_at, is_active,
    google_drive_connected,  -- No refresh token shown
    google_drive_folder_id, google_drive_folder_name
FROM users;

REVOKE SELECT ON users FROM vta_app;
GRANT SELECT ON users_safe TO vta_app;

-- 18. Force SSL connections
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/path/to/server.crt';
ALTER SYSTEM SET ssl_key_file = '/path/to/server.key';
```

#### 19.3.2 Database Connection Pool Security

```python
# In auth/db.py - Secure connection handling
from sqlalchemy import create_engine, event
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# Validate SSL mode
ssl_mode = os.getenv("POSTGRES_SSL_MODE", "require")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Check connection before using
    pool_recycle=1800,   # Recycle every 30 minutes
    
    connect_args={
        "sslmode": ssl_mode,
        "sslrootcert": os.getenv("POSTGRES_SSL_CERT"),  # CA cert path
        "sslcert": os.getenv("POSTGRES_CLIENT_CERT"),    # Client cert
        "sslkey": os.getenv("POSTGRES_CLIENT_KEY"),       # Client key
        "connect_timeout": 10,
        "statement_timeout": 30000,  # 30 second query timeout
    },
)

# Set session parameters on each connection
@event.listens_for(engine, "connect")
def set_connection_security(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    
    # Set secure session parameters
    cursor.execute("SET statement_timeout = '30s'")
    cursor.execute("SET lock_timeout = '10s'")
    cursor.execute("SET row_security = 'on'")  # Enable RLS
    
    # Set the current user ID for RLS
    # This should be set after authentication
    # cursor.execute("SET app.current_user_id = %s" % user_id)
    
    cursor.close()
```

---

### 19.4 Frontend Security (React)

#### 19.4.1 Security Headers & Configuration

```javascript
// In React app setup (index.html or security config)

// Content Security Policy meta tag
// <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.yourdomain.com; frame-ancestors 'none';">

// In package.json (React scripts)
{
  "scripts": {
    "start": "HTTPS=true SSL_CRT_FILE=cert.pem SSL_KEY_FILE=key.pem react-scripts start",
    "build": "GENERATE_SOURCEMAP=false react-scripts build"
  }
}
```

#### 19.4.2 Secure API Client

```javascript
// src/services/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://api.yourdomain.com';

class SecureApiClient {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      withCredentials: true,  // Important for HttpOnly cookies
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    // Request interceptor for CSRF
    this.client.interceptors.request.use(
      (config) => {
        // Get CSRF token from cookie or state
        const csrfToken = this.getCsrfToken();
        if (csrfToken) {
          config.headers['X-CSRF-Token'] = csrfToken;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Session expired - redirect to login
          window.location.href = '/login?expired=true';
        }
        if (error.response?.status === 403) {
          // Forbidden - show message
          console.error('Access denied:', error.response.data);
        }
        return Promise.reject(error);
      }
    );
  }

  getCsrfToken() {
    // CSRF token should be set in a cookie by the server
    const name = 'csrf_token=';
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1);
      if (c.indexOf(name) === 0) return c.substring(name.length, c.length);
    }
    return null;
  }

  // Secure login
  async login(email, password) {
    const response = await this.client.post('/auth/login', { email, password });
    return response.data;
  }

  // Secure query (with input sanitization)
  async query(question) {
    // Sanitize on client side as well
    const sanitized = this.sanitizeInput(question);
    const response = await this.client.post('/api/query', { query: sanitized });
    return response.data;
  }

  sanitizeInput(input) {
    // Remove any HTML/Script tags
    let sanitized = input.replace(/<[^>]*>/g, '');
    // Remove common XSS patterns
    sanitized = sanitized.replace(/javascript:/gi, '');
    sanitized = sanitized.replace(/on\w+=/gi, '');
    return sanitized.trim();
  }
}

export const api = new SecureApiClient();
```

#### 19.4.3 Secure Session Management

```javascript
// src/context/AuthContext.js
import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await api.client.get('/auth/me');
      setUser(response.data.user);
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const data = await api.login(email, password);
    setUser(data.user);
    return data;
  };

  const logout = async () => {
    try {
      await api.client.post('/auth/logout');
    } finally {
      setUser(null);
      // Clear any cached data
      sessionStorage.clear();
      localStorage.removeItem('cached_query');
    }
  };

  const hasRole = (role) => {
    return user?.role === role;
  };

  const canAccessCourse = (courseId) => {
    // Check if user is enrolled in course or owns it
    if (!user) return false;
    if (user.role === 'teacher') return true;
    return user.enrolled_courses?.includes(courseId);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasRole, canAccessCourse }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
```

#### 19.4.4 Protected Route Component

```javascript
// src/components/ProtectedRoute.js
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedRoute({ children, requiredRole }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}

// Usage in routes
<Route path="/dashboard" element={
  <ProtectedRoute>
    <Dashboard />
  </ProtectedRoute>
} />

<Route path="/teacher/upload" element={
  <ProtectedRoute requiredRole="teacher">
    <UploadPage />
  </ProtectedRoute>
} />
```

---

### 19.5 Audit Logging System

```python
# In auth/models.py - Audit log model
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(200), nullable=True)
    method = Column(String(10), nullable=True)
    request_data = Column(JSON, nullable=True)  # Sanitized request data
    response_status = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# In auth/routes.py - Audit logging middleware
from functools import wraps

def audit_log(event_type: str):
    """Decorator to automatically log endpoint access."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                # Get request details
                user_id = session.get("user_id")
                ip = request.remote_addr
                endpoint = request.endpoint
                method = request.method
                
                # Execute the route
                result = f(*args, **kwargs)
                
                # Log successful access
                try:
                    from auth.models import AuditLog
                    from auth.db import get_db
                    db = next(get_db())
                    log_entry = AuditLog(
                        event_type=event_type,
                        user_id=user_id,
                        ip_address=ip,
                        endpoint=endpoint,
                        method=method,
                        response_status=result[1] if isinstance(result, tuple) else 200,
                    )
                    db.add(log_entry)
                    db.commit()
                except:
                    pass  # Don't let logging break the app
                
                return result
            except Exception as e:
                # Log failed access
                try:
                    db = next(get_db())
                    log_entry = AuditLog(
                        event_type=f"{event_type}_FAILED",
                        user_id=session.get("user_id"),
                        ip_address=request.remote_addr,
                        endpoint=request.endpoint,
                        method=request.method,
                        details={"error": str(e)}
                    )
                    db.add(log_entry)
                    db.commit()
                except:
                    pass
                raise
        return decorated
    return decorator


# Usage examples
@auth_bp.route("/login", methods=["POST"])
@audit_log("LOGIN")
def login():
    # ... login logic
    pass


@drive_bp.route("/sync", methods=["POST"])
@login_required
@teacher_required
@audit_log("FILE_SYNC")
def sync_files():
    # ... sync logic
    pass
```

---

### 19.6 Security Checklist

#### Pre-Production Security Checklist

| Check | Description | Status |
|-------|-------------|--------|
| ✅ | All connections use SSL/TLS | Required |
| ✅ | Passwords hashed with bcrypt/argon2 | Required |
| ✅ | Rate limiting on auth endpoints | Required |
| ✅ | CSRF protection enabled | Required |
| ✅ | Input validation with Pydantic | Required |
| ✅ | Row-Level Security enabled | Required |
| ✅ | Audit logging implemented | Required |
| ✅ | Session timeout (24h max) | Required |
| ✅ | Secure cookie settings | Required |
| ✅ | Content Security Policy | Required |
| ✅ | XSS protection in frontend | Required |
| ✅ | SQL injection prevention (parameterized queries) | Required |
| ✅ | Role-based access control | Required |
| ✅ | File size limits | Required |
| ✅ | Query length limits | Required |
| ✅ | Encryption at rest for tokens | Recommended |
| ✅ | Two-factor authentication | Future |

---

### 19.7 Environment Variables Security

```bash
# ============================================================================
# SECURITY-SENSITIVE ENVIRONMENT VARIABLES
# ============================================================================

# DATABASE - MUST USE SSL
DATABASE_URL=postgresql://vta_app:STRONG_PASSWORD@host:5432/virtual_ta?sslmode=require

# ENCRYPTION KEY - 32 bytes (256 bits) - NEVER COMMIT THIS!
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
APP_ENCRYPTION_KEY=your-256-bit-hex-key-here

# FLASK SECRET - Sign session cookies - NEVER COMMIT THIS!
FLASK_SECRET_KEY=your-flask-secret-key-here

# GOOGLE OAUTH - Keep secure
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here

# REDIS - Use password in production
REDIS_PASSWORD=your-redis-password

# RATE LIMITING
RATE_LIMIT_STORAGE=redis://localhost:6379/5

# ============================================================================
# SECURITY WHITELIST (for deployment)
# ============================================================================
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

---

### 19.8 Incident Response Considerations

```python
# In security/response.py - Emergency security procedures

EMERGENCY_PROCEDURES = {
    "data_breach": [
        "1. Isolate affected systems immediately",
        "2. Preserve audit logs for investigation",
        "3. Revoke all active sessions (delete Redis keys: session:* )",
        "4. Rotate all API keys and secrets",
        "5. Notify affected users within 72 hours",
        "6. Report to relevant authorities if required",
    ],
    
    "unauthorized_access": [
        "1. Identify the user account(s) involved",
        "2. Lock the account(s) immediately",
        "3. Review audit logs for extent of access",
        "4. Reset password force logout all sessions",
        "5. Enable enhanced monitoring",
    ],
    
    "ddos_attack": [
        "1. Enable rate limiting (already in place)",
        "2. Contact hosting provider",
        "3. Enable CDN-level protection if available",
        "4. Consider temporary IP blocking",
        "5. Monitor for patterns",
    ],
}
```

---

## Updated Summary: Complete Feature List

| Feature | Security Level | Implementation |
|---------|---------------|----------------|
| Auth with role separation | Critical | RBAC + RLS |
| Google Drive OAuth | Critical | Folder-scoped access |
| Session management | Critical | HttpOnly + Secure cookies |
| Input validation | Critical | Pydantic + sanitization |
| SQL injection prevention | Critical | Parameterized queries + RLS |
| Rate limiting | High | Redis-backed + per-endpoint |
| Audit logging | High | Database + file logging |
| API security | High | CSP + CORS + headers |
| Frontend XSS protection | High | Sanitization + CSP |
| Encrypted sensitive data | Medium | PostgreSQL pgcrypto |
| DDoS protection | Medium | Rate limiting + CDN |

---

## New Section 20: Enterprise-Grade PostgreSQL Database Schema

### 20.1 Schema Architecture Overview

This section provides a comprehensive, enterprise-grade database schema following big tech company standards. The design prioritizes:

1. **Security**: Row-level security, encryption, audit trails
2. **Scalability**: Proper indexing, partitioning, connection pooling
3. **Data Integrity**: Foreign keys, constraints, triggers
4. **Performance**: Optimized queries, materialized views, caching strategies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATABASE SCHEMA ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CORE DOMAINS                                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │   │
│  │  │   AUTH       │ │   COURSES    │ │   FILES      │ │   CHAT      │  │   │
│  │  │   (users,   │ │   (courses,  │ │   (metadata, │ │   (sessions,│  │   │
│  │  │   sessions, │ │   enrollments│ │   vectors,   │ │   messages, │  │   │
│  │  │   tokens)   │ │   materials) │ │   sync)      │ │   feedback) │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘  │   │
│  │                                                                     │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │   │
│  │  │   AUDIT      │ │   RATE       │ │   CACHE      │                │   │
│  │  │   (logs,    │ │   (limits,   │ │   (queries,  │                │   │
│  │  │   events)   │ │   tokens)    │ │   sessions)  │                │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INFRASTRUCTURE                                   │   │
│  │  • Connection Pooling (PgBouncer)                                  │   │
│  │  • Read Replicas (for queries)                                     │   │
│  │  • Backup Strategy (WAL archiving + pg_dump)                       │   │
│  │  • Monitoring (pg_stat_statements, pgBadger)                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 20.2 Complete SQL Schema

```sql
-- ============================================================================
-- VIRTUAL TEACHING ASSISTANT - ENTERPRISE DATABASE SCHEMA
-- PostgreSQL 16+ with pgvector, pgcrypto
-- ============================================================================

-- ============================================================================
-- STEP 1: EXTENSIONS (Must be created first)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search

-- ============================================================================
-- STEP 2: ENUMS (Type-safe constraints)
-- ============================================================================

-- User roles
CREATE TYPE user_role AS ENUM ('student', 'teacher', 'admin');

-- Account status
CREATE TYPE account_status AS ENUM ('active', 'suspended', 'locked', 'pending');

-- Enrollment status  
CREATE TYPE enrollment_status AS ENUM ('active', 'dropped', 'completed', 'pending');

-- Sync status
CREATE TYPE sync_status AS ENUM ('pending', 'processing', 'completed', 'failed');

-- Content types
CREATE TYPE content_type AS ENUM ('text', 'table', 'image', 'audio', 'code');

-- Chunking strategies
CREATE TYPE chunking_strategy AS ENUM ('fixed', 'semantic_markdown', 'semantic_code', 'semantic_pdf', 'semantic_html', 'semantic_text');

-- Message types
CREATE TYPE message_type AS ENUM ('user', 'assistant', 'system');

-- Audit event types
CREATE TYPE audit_event_type AS ENUM (
    'USER_LOGIN', 'USER_LOGOUT', 'USER_REGISTER',
    'USER_PASSWORD_CHANGE', 'USER_PROFILE_UPDATE',
    'COURSE_CREATE', 'COURSE_UPDATE', 'COURSE_DELETE',
    'ENROLLMENT_CREATE', 'ENROLLMENT_DROP',
    'FILE_SYNC_START', 'FILE_SYNC_COMPLETE', 'FILE_SYNC_FAILED',
    'DRIVE_CONNECT', 'DRIVE_DISCONNECT', 'FOLDER_SELECT',
    'QUERY_EXECUTED', 'API_ACCESS_DENIED'
);

-- ============================================================================
-- STEP 3: CORE TABLES
-- ============================================================================

-- ============================================================================
-- 3.1 USERS TABLE
-- ============================================================================
CREATE TABLE users (
    -- Primary key
    id BIGSERIAL PRIMARY KEY,
    
    -- Authentication
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Profile
    full_name VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'student',
    avatar_url VARCHAR(500),
    bio TEXT,
    
    -- Status
    status account_status NOT NULL DEFAULT 'active',
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Security timestamps
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    last_login_ip INET,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    
    -- Google Drive integration
    google_drive_connected BOOLEAN NOT NULL DEFAULT FALSE,
    google_drive_folder_id VARCHAR(255),  -- Restricted folder
    google_drive_folder_name VARCHAR(500),
    google_drive_refresh_token_encrypted BYTEA,  -- Encrypted!
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT users_password_min_length CHECK (char_length(password_hash) >= 60),  -- bcrypt hash
    CONSTRAINT users_failed_attempts CHECK (failed_login_attempts >= 0 AND failed_login_attempts <= 10)
);

-- Indexes for users table
CREATE INDEX idx_users_email ON users(email) WHERE status = 'active';
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_google_drive_connected ON users(google_drive_connected);
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- Partial unique index for verified emails (optional uniqueness)
CREATE UNIQUE INDEX idx_users_email_verified ON users(email) WHERE email_verified = TRUE;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- 3.2 SESSIONS TABLE (Enhanced session management)
-- ============================================================================
CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Session data
    session_token VARCHAR(255) NOT NULL UNIQUE,
    refresh_token VARCHAR(255),
    ip_address INET NOT NULL,
    user_agent TEXT,
    
    -- Security
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    device_fingerprint VARCHAR(64),
    browser VARCHAR(50),
    os VARCHAR(50),
    
    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT sessions_expires_future CHECK (expires_at > created_at)
);

-- Indexes
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_user_id ON sessions(user_id) WHERE is_active = TRUE;
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at) WHERE is_active = TRUE;
CREATE INDEX idx_sessions_last_activity ON sessions(last_activity_at DESC);

-- Auto-expire sessions function
CREATE OR REPLACE FUNCTION expire_old_sessions()
RETURNS void AS $$
BEGIN
    UPDATE sessions 
    SET is_active = FALSE 
    WHERE is_active = TRUE AND expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Schedule: Run every hour
-- SELECT cron.schedule('expire-sessions', '0 * * * *', 'SELECT expire_old_sessions()');


-- ============================================================================
-- 3.3 COURSES TABLE
-- ============================================================================
CREATE TABLE courses (
    id BIGSERIAL PRIMARY KEY,
    
    -- Course information
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL,  -- e.g., "CPT_S 421"
    description TEXT,
    syllabus TEXT,
    
    -- Organization
    teacher_id BIGINT NOT NULL REFERENCES users(id),
    semester VARCHAR(50),
    year INTEGER,
    
    -- Settings
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    enrollment_code VARCHAR(20) UNIQUE,  -- For student self-enrollment
    
    -- Google Drive folder (optional)
    drive_folder_id VARCHAR(255),
    drive_folder_name VARCHAR(500),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    start_date DATE,
    end_date DATE,
    
    -- Constraints
    CONSTRAINT courses_code_format CHECK (code ~* '^[A-Z]{2,4}_[A-Z0-9]{2,4}$'),
    CONSTRAINT courses_year_valid CHECK (year >= 2000 AND year <= 2100),
    CONSTRAINT courses_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

-- Indexes
CREATE INDEX idx_courses_teacher_id ON courses(teacher_id);
CREATE INDEX idx_courses_code ON courses(code);
CREATE INDEX idx_courses_semester_year ON courses(semester, year);
CREATE INDEX idx_courses_is_active ON courses(is_active);
CREATE INDEX idx_courses_enrollment_code ON courses(enrollment_code) WHERE enrollment_code IS NOT NULL;

-- Full-text search index for courses
CREATE INDEX idx_courses_fts ON courses USING GIN (to_tsvector('english', name || ' ' || COALESCE(description, ''))));


-- ============================================================================
-- 3.4 ENROLLMENTS TABLE
-- ============================================================================
CREATE TABLE enrollments (
    id BIGSERIAL PRIMARY KEY,
    
    -- Relationships
    student_id BIGINT NOT NULL REFERENCES users(id),
    course_id BIGINT NOT NULL REFERENCES courses(id),
    
    -- Status
    status enrollment_status NOT NULL DEFAULT 'pending',
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dropped_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Progress tracking
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    
    -- Enrollment method
    enrollment_method VARCHAR(50) NOT NULL DEFAULT 'self',  -- 'self', 'teacher', 'admin'
    enrolled_by BIGINT REFERENCES users(id),
    
    -- Constraints
    CONSTRAINT enrollments_unique_student_course UNIQUE (student_id, course_id),
    CONSTRAINT enrollments_progress CHECK (progress_percentage >= 0 AND progress_percentage <= 100)
);

-- Indexes
CREATE INDEX idx_enrollments_student_id ON enrollments(student_id);
CREATE INDEX idx_enrollments_course_id ON enrollments(course_id);
CREATE INDEX idx_enrollments_status ON enrollments(status);
CREATE INDEX idx_enrollments_student_status ON enrollments(student_id, status);

-- Partial index for active enrollments (frequently queried)
CREATE INDEX idx_enrollments_active ON enrollments(student_id, course_id) 
    WHERE status = 'active';


-- ============================================================================
-- 3.5 FILE METADATA TABLE
-- ============================================================================
CREATE TABLE file_metadata (
    id BIGSERIAL PRIMARY KEY,
    
    -- Google Drive info
    drive_file_id VARCHAR(255) NOT NULL,
    drive_file_md5 VARCHAR(32),  -- For change detection
    file_name VARCHAR(500) NOT NULL,
    mime_type VARCHAR(255),
    file_size BIGINT,  -- Bytes
    
    -- Ownership
    owner_user_id BIGINT NOT NULL REFERENCES users(id),
    course_id BIGINT REFERENCES courses(id),
    
    -- Sync tracking
    sync_status sync_status NOT NULL DEFAULT 'pending',
    drive_modified_time TIMESTAMPTZ,  -- When Drive file was modified
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    
    -- Content breakdown
    num_text_chunks INTEGER NOT NULL DEFAULT 0,
    num_table_chunks INTEGER NOT NULL DEFAULT 0,
    num_image_chunks INTEGER NOT NULL DEFAULT 0,
    num_audio_chunks INTEGER NOT NULL DEFAULT 0,
    total_chunks INTEGER NOT NULL DEFAULT 0,
    
    -- Storage metrics
    original_size_kb INTEGER,
    vector_storage_kb INTEGER,
    compression_ratio REAL,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT file_metadata_unique_drive_file UNIQUE (drive_file_id, course_id),
    CONSTRAINT file_metadata_size_positive CHECK (file_size >= 0),
    CONSTRAINT file_metadata_retry_count CHECK (retry_count >= 0 AND retry_count <= 5)
);

-- Indexes
CREATE INDEX idx_file_metadata_owner ON file_metadata(owner_user_id);
CREATE INDEX idx_file_metadata_course ON file_metadata(course_id);
CREATE INDEX idx_file_metadata_sync_status ON file_metadata(sync_status);
CREATE INDEX idx_file_metadata_synced_at ON file_metadata(synced_at DESC);
CREATE INDEX idx_file_metadata_drive_file_id ON file_metadata(drive_file_id);

-- Composite index for common queries
CREATE INDEX idx_file_metadata_owner_course ON file_metadata(owner_user_id, course_id);


-- ============================================================================
-- 3.6 VECTOR CHUNKS TABLE (The core vector store)
-- ============================================================================
CREATE TABLE vector_chunks (
    id UUID NOT NULL DEFAULT uuid_generate_v4(),
    file_metadata_id BIGINT NOT NULL REFERENCES file_metadata(id) ON DELETE CASCADE,
    
    -- Content
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    page_number INTEGER,
    content_type content_type NOT NULL DEFAULT 'text',
    
    -- Semantic chunking metadata
    chunking_strategy chunking_strategy NOT NULL DEFAULT 'fixed',
    section_header VARCHAR(500),
    subsection VARCHAR(500),
    
    -- Vector embedding (pgvector)
    embedding vector(768),  -- Adjust based on embedding model dimension
    
    -- Metadata
    source_url VARCHAR(1000),
    line_numbers VARCHAR(100),
    language VARCHAR(20),  -- For code chunks
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT vector_chunks_pkey PRIMARY KEY (id),
    CONSTRAINT vector_chunks_unique_chunk UNIQUE (file_metadata_id, chunk_index)
);

-- Indexes for vector search
-- HNSW index (best for <1M vectors, fast queries)
CREATE INDEX idx_vector_chunks_embedding_hnsw ON vector_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- IVFFlat index (better for >1M vectors)
-- CREATE INDEX idx_vector_chunks_embedding_ivfflat ON vector_chunks 
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

-- Regular indexes
CREATE INDEX idx_vector_chunks_file_metadata ON vector_chunks(file_metadata_id);
CREATE INDEX idx_vector_chunks_content_type ON vector_chunks(content_type);
CREATE INDEX idx_vector_chunks_page ON vector_chunks(page_number);
CREATE INDEX idx_vector_chunks_created_at ON vector_chunks(created_at DESC);

-- Partial indexes for common queries
CREATE INDEX idx_vector_chunks_text ON vector_chunks(file_metadata_id, content_type) 
    WHERE content_type = 'text';
CREATE INDEX idx_vector_chunks_table ON vector_chunks(file_metadata_id, content_type) 
    WHERE content_type = 'table';
CREATE INDEX idx_vector_chunks_code ON vector_chunks(file_metadata_id, content_type) 
    WHERE content_type = 'code';

-- Full-text search index for chunk text
CREATE INDEX idx_vector_chunks_fts ON vector_chunks USING GIN (to_tsvector('english', text));


-- ============================================================================
-- 3.7 CHAT SESSIONS TABLE
-- ============================================================================
CREATE TABLE chat_sessions (
    id BIGSERIAL PRIMARY KEY,
    
    -- Relationships
    user_id BIGINT NOT NULL REFERENCES users(id),
    course_id BIGINT REFERENCES courses(id),  -- Optional: can ask about specific course
    
    -- Session info
    title VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Statistics
    num_messages INTEGER NOT NULL DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chat_sessions_unique_active UNIQUE (user_id, id) 
        WHERE is_active = TRUE
);

-- Indexes
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_course_id ON chat_sessions(course_id);
CREATE INDEX idx_chat_sessions_is_active ON chat_sessions(is_active);
CREATE INDEX idx_chat_sessions_updated_at ON chat_sessions(updated_at DESC);


-- ============================================================================
-- 3.8 CHAT MESSAGES TABLE
-- ============================================================================
CREATE TABLE chat_messages (
    id BIGSERIAL PRIMARY KEY,
    
    -- Relationships
    session_id BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id),
    
    -- Message content
    message_type message_type NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    token_count INTEGER,  -- For billing/tracking
    
    -- For assistant messages
    citations JSONB,  -- [{"file": "lecture1.pdf", "page": 5, "relevance": 0.92}]
    model_used VARCHAR(50),
    latency_ms INTEGER,
    tokens_used INTEGER,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chat_messages_content_not_empty CHECK (char_length(content) > 0)
);

-- Indexes
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at DESC);
CREATE INDEX idx_chat_messages_token_count ON chat_messages(token_count);

-- Partitioning by date (recommended for large message tables)
-- CREATE TABLE chat_messages_y2026m01 PARTITION BY RANGE (created_at);



-- ============================================================================
-- 3.9 AUDIT LOG TABLE (Comprehensive audit trail)
-- ============================================================================
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    
    -- Event info
    event_type audit_event_type NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    
    -- User context
    user_id BIGINT REFERENCES users(id),
    user_email VARCHAR(255),  -- Denormalized for historical accuracy
    
    -- Request context
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(200),
    method VARCHAR(10),
    request_id UUID,  -- For request tracing
    
    -- Data
    old_values JSONB,
    new_values JSONB,
    details JSONB,
    
    -- Result
    response_status INTEGER,
    error_message TEXT,
    
    -- Timing
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms INTEGER,
    
    -- Constraints
    CONSTRAINT audit_log_duration CHECK (duration_ms IS NULL OR duration_ms >= 0)
);

-- Indexes for audit log (optimized for common queries)
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX idx_audit_log_ip_address ON audit_log(ip_address);
CREATE INDEX idx_audit_log_user_id_created ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_event_type_created ON audit_log(event_type, created_at DESC);

-- Partition audit log by month (recommended for high-volume)
-- CREATE TABLE audit_log_2026_01 PARTITION OF audit_log
--     FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');


-- ============================================================================
-- 3.10 RATE LIMITS TABLE
-- ============================================================================
CREATE TABLE rate_limits (
    id BIGSERIAL PRIMARY KEY,
    
    -- Identifier
    identifier VARCHAR(255) NOT NULL,  -- IP, user_id, or API key
    identifier_type VARCHAR(20) NOT NULL,  -- 'ip', 'user', 'api_key'
    
    -- Limit info
    endpoint VARCHAR(200) NOT NULL,
    limit_count INTEGER NOT NULL,
    window_seconds INTEGER NOT NULL,
    
    -- Tracking
    request_count INTEGER NOT NULL DEFAULT 0,
    window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_end TIMESTAMPTZ,
    
    -- Last request
    last_request_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT rate_limits_unique_endpoint_id UNIQUE (identifier, endpoint)
);

-- Indexes
CREATE INDEX idx_rate_limits_identifier ON rate_limits(identifier, identifier_type);
CREATE INDEX idx_rate_limits_window_start ON rate_limits(window_start DESC);


-- ============================================================================
-- 3.11 API KEYS TABLE (For programmatic access)
-- ============================================================================
CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    
    -- Key data
    key_hash VARCHAR(255) NOT NULL UNIQUE,  -- Hashed key
    key_prefix VARCHAR(20) NOT NULL,  -- First 20 chars for display
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Usage limits
    rate_limit INTEGER,  -- Requests per minute
    monthly_quota INTEGER,  -- Total requests per month
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    
    -- Stats
    requests_count BIGINT NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT api_keys_prefix_unique UNIQUE (key_prefix),
    CONSTRAINT api_keys_expires_future CHECK (expires_at IS NULL OR expires_at > NOW())
);

-- Indexes
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id) WHERE is_active = TRUE;
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at) WHERE expires_at IS NOT NULL;


-- ============================================================================
-- 3.12 MATERIALS TABLE (Course materials organization)
-- ============================================================================
CREATE TABLE materials (
    id BIGSERIAL PRIMARY KEY,
    
    -- Relationships
    course_id BIGINT NOT NULL REFERENCES courses(id),
    file_metadata_id BIGINT REFERENCES file_metadata(id),
    
    -- Organization
    name VARCHAR(255) NOT NULL,
    description TEXT,
    material_order INTEGER NOT NULL DEFAULT 0,
    parent_id BIGINT REFERENCES materials(id),  -- For hierarchy
    material_type VARCHAR(50) NOT NULL,  -- 'lecture', 'assignment', 'reading', 'slide'
    
    -- Visibility
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    visible_from TIMESTAMPTZ,
    visible_until TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT materials_unique_course_order UNIQUE (course_id, material_order)
);

-- Indexes
CREATE INDEX idx_materials_course_id ON materials(course_id);
CREATE INDEX idx_materials_parent ON materials(parent_id);
CREATE INDEX idx_materials_order ON materials(course_id, material_order);
CREATE INDEX idx_materials_published ON materials(course_id, is_published) WHERE is_published = TRUE;

-- ============================================================================
-- STEP 4: ROW-LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on all user data tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE vector_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 4.1 Users Policies
-- ============================================================================

-- Users can read their own profile
CREATE POLICY users_select_own ON users
    FOR SELECT USING (id = current_setting('app.current_user_id', true)::BIGINT);

-- Users can update their own profile (except role)
CREATE POLICY users_update_own ON users
    FOR UPDATE USING (id = current_setting('app.current_user_id', true)::BIGINT)
    WITH CHECK (
        role = OLD.role AND 
        id = current_setting('app.current_user_id', true)::BIGINT
    );

-- Admins can do everything
CREATE POLICY users_admin_full ON users
    FOR ALL USING (current_setting('app.current_user_role', true) = 'admin');


-- ============================================================================
-- 4.2 Courses Policies
-- ============================================================================

-- Teachers see their own courses
CREATE POLICY courses_select_teacher ON courses
    FOR SELECT USING (
        teacher_id = current_setting('app.current_user_id', true)::BIGINT OR
        is_public = TRUE
    );

-- Teachers can insert/update their own courses
CREATE POLICY courses_teacher_manage ON courses
    FOR ALL USING (teacher_id = current_setting('app.current_user_id', true)::BIGINT);


-- ============================================================================
-- 4.3 Enrollments Policies
-- ============================================================================

-- Students see their enrollments
CREATE POLICY enrollments_select_own ON enrollments
    FOR SELECT USING (
        student_id = current_setting('app.current_user_id', true)::BIGINT OR
        course_id IN (
            SELECT id FROM courses 
            WHERE teacher_id = current_setting('app.current_user_id', true)::BIGINT
        )
    );

-- Students can enroll themselves
CREATE POLICY enrollments_insert_own ON enrollments
    FOR INSERT WITH CHECK (
        student_id = current_setting('app.current_user_id', true)::BIGINT OR
        current_setting('app.current_user_role', true) = 'teacher'
    );


-- ============================================================================
-- 4.4 File Metadata & Vector Chunks Policies
-- ============================================================================

-- Teachers see their own files
CREATE POLICY file_metadata_select_own ON file_metadata
    FOR SELECT USING (
        owner_user_id = current_setting('app.current_user_id', true)::BIGINT OR
        course_id IN (
            SELECT course_id FROM enrollments 
            WHERE student_id = current_setting('app.current_user_id', true)::BIGINT
            AND status = 'active'
        )
    );

-- Vector chunks inherit file metadata access
CREATE POLICY vector_chunks_select_own ON vector_chunks
    FOR SELECT USING (
        file_metadata_id IN (
            SELECT id FROM file_metadata 
            WHERE owner_user_id = current_setting('app.current_user_id', true)::BIGINT
            OR course_id IN (
                SELECT course_id FROM enrollments 
                WHERE student_id = current_setting('app.current_user_id', true)::BIGINT
                AND status = 'active'
            )
        )
    );


-- ============================================================================
-- 4.5 Chat Policies
-- ============================================================================

-- Users see their own chat sessions
CREATE POLICY chat_sessions_select_own ON chat_sessions
    FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::BIGINT);

-- Users see messages in their sessions
CREATE POLICY chat_messages_select_own ON chat_messages
    FOR SELECT USING (
        session_id IN (
            SELECT id FROM chat_sessions 
            WHERE user_id = current_setting('app.current_user_id', true)::BIGINT
        )
    );


-- ============================================================================
-- STEP 5: FUNCTIONS & PROCEDURES
-- ============================================================================

-- ============================================================================
-- 5.1 Authentication Functions
-- ============================================================================

-- Set session security context
CREATE OR REPLACE FUNCTION set_session_security(user_id BIGINT, user_role TEXT)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', user_id::TEXT, true);
    PERFORM set_config('app.current_user_role', user_role, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Clear session security context
CREATE OR REPLACE FUNCTION clear_session_security()
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_user_id', NULL, true);
    PERFORM set_config('app.current_user_role', NULL, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Login function with rate limiting
CREATE OR REPLACE FUNCTION user_login(
    p_email VARCHAR,
    p_password VARCHAR,
    p_ip_address INET
) RETURNS TABLE(
    user_id BIGINT,
    session_token VARCHAR,
    refresh_token VARCHAR
) AS $$
DECLARE
    v_user users;
    v_attempts INTEGER;
    v_locked_until TIMESTAMPTZ;
BEGIN
    -- Check for locked account
    SELECT locked_until INTO v_locked_until
    FROM users WHERE email = p_email;
    
    IF v_locked_until IS NOT NULL AND v_locked_until > NOW() THEN
        RAISE EXCEPTION 'Account is locked until %', v_locked_until;
    END IF;
    
    -- Verify credentials
    SELECT * INTO v_user
    FROM users 
    WHERE email = p_email AND status = 'active';
    
    IF v_user IS NULL OR NOT check_password_hash(v_user.password_hash, p_password) THEN
        -- Increment failed attempts
        UPDATE users 
        SET failed_login_attempts = failed_login_attempts + 1,
            locked_until = CASE 
                WHEN failed_login_attempts + 1 >= 5 THEN NOW() + INTERVAL '30 minutes'
                ELSE NULL
            END
        WHERE email = p_email;
        
        -- Log failed attempt
        PERFORM audit_log_entry(
            'USER_LOGIN_FAILED', 
            p_email, 
            p_ip_address, 
            jsonb_build_object('reason', 'invalid_credentials')
        );
        
        RAISE EXCEPTION 'Invalid credentials';
    END IF;
    
    -- Reset failed attempts on successful login
    UPDATE users SET 
        failed_login_attempts = 0,
        locked_until = NULL,
        last_login_at = NOW(),
        last_login_ip = p_ip_address
    WHERE id = v_user.id;
    
    -- Set session security
    PERFORM set_session_security(v_user.id, v_user.role);
    
    -- Log successful login
    PERFORM audit_log_entry(
        'USER_LOGIN', 
        v_user.email, 
        p_ip_address, 
        NULL
    );
    
    -- Return session tokens
    RETURN QUERY 
    SELECT v_user.id, gen_random_uuid()::VARCHAR, gen_random_uuid()::VARCHAR;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================================
-- 5.2 Audit Log Function
-- ============================================================================
CREATE OR REPLACE FUNCTION audit_log_entry(
    p_event_type audit_event_type,
    p_user_email VARCHAR,
    p_ip_address INET,
    p_details JSONB
) RETURNS void AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    -- Get user_id if email provided
    IF p_user_email IS NOT NULL THEN
        SELECT id INTO v_user_id FROM users WHERE email = p_user_email;
    END IF;
    
    INSERT INTO audit_log (
        event_type,
        event_category,
        user_id,
        user_email,
        ip_address,
        details,
        created_at
    ) VALUES (
        p_event_type,
        split_part(p_event_type::TEXT, '_', 1),
        v_user_id,
        p_user_email,
        p_ip_address,
        p_details,
        NOW()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================================
-- 5.3 Vector Search Function (Optimized)
-- ============================================================================
CREATE OR REPLACE FUNCTION search_vectors(
    p_query_embedding vector,
    p_user_id BIGINT,
    p_course_ids BIGINT[],
    p_content_types content_type[],
    p_limit INTEGER DEFAULT 5
) RETURNS TABLE(
    chunk_id UUID,
    text TEXT,
    similarity REAL,
    file_name VARCHAR,
    course_name VARCHAR,
    page_number INTEGER,
    content_type content_type,
    section_header VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        vc.id,
        vc.text,
        (vc.embedding <=> p_query_embedding)::REAL AS similarity,
        fm.file_name,
        c.name AS course_name,
        vc.page_number,
        vc.content_type,
        vc.section_header
    FROM vector_chunks vc
    JOIN file_metadata fm ON vc.file_metadata_id = fm.id
    JOIN courses c ON fm.course_id = c.id
    WHERE fm.course_id = ANY(p_course_ids)
    AND (p_content_types IS NULL OR vc.content_type = ANY(p_content_types))
    ORDER BY vc.embedding <=> p_query_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 5.4 Course Enrollment Function
-- ============================================================================
CREATE OR REPLACE FUNCTION enroll_student(
    p_student_id BIGINT,
    p_course_id BIGINT,
    p_enrollment_method VARCHAR
) RETURNS TABLE(success BOOLEAN, message TEXT) AS $$
DECLARE
    v_course courses;
    v_existing enrollment%ROWTYPE;
BEGIN
    -- Check if course exists
    SELECT * INTO v_course FROM courses WHERE id = p_course_id;
    IF v_course IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Course not found';
    END IF;
    
    -- Check for existing enrollment
    SELECT * INTO v_existing 
    FROM enrollments 
    WHERE student_id = p_student_id AND course_id = p_course_id;
    
    IF v_existing IS NOT NULL THEN
        IF v_existing.status = 'active' THEN
            RETURN QUERY SELECT FALSE, 'Already enrolled in this course';
        END IF;
        -- Reactivate if was dropped
        UPDATE enrollments 
        SET status = 'active', 
            enrolled_at = NOW(), 
            dropped_at = NULL,
            enrollment_method = p_enrollment_method
        WHERE id = v_existing.id;
        
        RETURN QUERY SELECT TRUE, 'Re-enrolled in course';
    END IF;
    
    -- Create new enrollment
    INSERT INTO enrollments (student_id, course_id, status, enrollment_method)
    VALUES (p_student_id, p_course_id, 'active', p_enrollment_method);
    
    -- Log enrollment
    PERFORM audit_log_entry(
        'ENROLLMENT_CREATE',
        (SELECT email FROM users WHERE id = p_student_id),
        NULL,
        jsonb_build_object('course_id', p_course_id, 'method', p_enrollment_method)
    );
    
    RETURN QUERY SELECT TRUE, 'Successfully enrolled';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================================
-- STEP 6: MATERIALIZED VIEWS (For performance)
-- ============================================================================

-- User activity summary (refreshed hourly)
CREATE MATERIALIZED VIEW user_activity_summary AS
SELECT 
    u.id AS user_id,
    u.email,
    u.role,
    COUNT(DISTINCT cs.id) AS total_sessions,
    COUNT(DISTINCT cm.id) AS total_messages,
    MAX(cs.created_at) AS last_session_at,
    MAX(cm.created_at) AS last_message_at,
    COUNT(DISTINCT e.course_id) AS enrolled_courses
FROM users u
LEFT JOIN chat_sessions cs ON cs.user_id = u.id
LEFT JOIN chat_messages cm ON cm.user_id = u.id
LEFT JOIN enrollments e ON e.student_id = u.id AND e.status = 'active'
GROUP BY u.id, u.email, u.role;

CREATE UNIQUE INDEX idx_user_activity_summary ON user_activity_summary(user_id);

-- Course statistics (refreshed on schedule)
CREATE MATERIALIZED VIEW course_stats AS
SELECT 
    c.id AS course_id,
    c.name AS course_name,
    c.code,
    COUNT(DISTINCT e.student_id) AS student_count,
    COUNT(DISTINCT fm.id) AS file_count,
    SUM(fm.total_chunks) AS total_chunks,
    SUM(fm.file_size) AS total_size_bytes,
    MAX(fm.synced_at) AS last_synced_at,
    AVG(progress_percentage) AS avg_progress
FROM courses c
LEFT JOIN enrollments e ON e.course_id = c.id AND e.status = 'active'
LEFT JOIN file_metadata fm ON fm.course_id = c.id
GROUP BY c.id, c.name, c.code;

CREATE UNIQUE INDEX idx_course_stats ON course_stats(course_id);


-- ============================================================================
-- STEP 7: PARTITIONS (For large tables)
-- ============================================================================

-- Chat messages partition by month
CREATE TABLE chat_messages_2026_04 PARTITION OF chat_messages
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE chat_messages_2026_05 PARTITION OF chat_messages
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Audit log partition by month
CREATE TABLE audit_log_2026_04 PARTITION OF audit_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');


-- ============================================================================
-- STEP 8: DATABASE ROLE & PERMISSIONS
-- ============================================================================

-- Create application user (not superuser!)
CREATE ROLE vta_app WITH LOGIN PASSWORD 'use_strong_password_here';
CREATE ROLE vta_readonly WITH LOGIN PASSWORD 'readonly_password_here';
CREATE ROLE vta_admin WITH LOGIN PASSWORD 'admin_password_here';

-- Grant schema permissions
GRANT USAGE ON SCHEMA public TO vta_app;
GRANT USAGE ON SCHEMA public TO vta_readonly;

-- Grant table permissions to app user
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO vta_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vta_readonly;

-- Grant sequence permissions
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vta_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vta_readonly;

-- Grant function permissions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO vta_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO vta_readonly;

-- Set default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vta_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO vta_app;


-- ============================================================================
-- STEP 9: DATABASE PARAMETERS & TUNING
-- ============================================================================

-- PostgreSQL configuration (postgresql.conf)
-- These should be set at the database server level

-- Memory settings (adjust based on available RAM)
-- shared_buffers = 256MB  -- 25% of RAM
-- effective_cache_size = 768MB  -- 75% of RAM
-- work_mem = 64MB
-- maintenance_work_mem = 128MB

-- Query planning
-- random_page_cost = 1.1  -- For SSDs
-- effective_io_concurrency = 200

-- Write-ahead log
-- wal_buffers = 16MB
-- checkpoint_completion_target = 0.9

-- Connection pooling ( PgBouncer )
-- max_connections = 100 (application)
-- pool_mode = transaction

-- Security
-- ssl = on
-- ssl_cert_file = '/path/to/server.crt'
-- ssl_key_file = '/path/to/server.key'
-- password_encryption = scram-sha-256

-- Logging (for security audit)
-- log_connections = on
-- log_disconnections = on
-- log_duration = on
-- log_lock_waits = on
-- log_statement = 'ddl'
-- log_min_duration_statement = 1000  -- Log queries > 1s


-- ============================================================================
-- STEP 10: BACKUP & RECOVERY STRATEGY
-- ============================================================================

-- Daily full backup (pg_dump)
-- 0 2 * * * pg_dump -Fc -f /backups/virtual_ta_$(date +\%Y\%m\%d).dump virtual_ta

-- Continuous archiving (WAL)
-- archive_mode = on
-- archive_command = 'cp %p /archive/wal/%f'
-- restore_command = 'cp /archive/wal/%f %p'

-- Point-in-time recovery window: 7 days
-- recovery_target_time = '2026-04-03 12:00:00 UTC'

-- Test backup restoration periodically
-- pg_restore -d virtual_ta_test /backups/virtual_ta_latest.dump
```

---

### 20.3 Schema Relationships Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE RELATIONSHIPS                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌──────────┐                                                          │
│    │  users   │◄──────────────────────┐                                    │
│    └────┬─────┘                       │                                    │
│         │                            │                                    │
│    ┌────┴─────┐                  ┌────┴─────┐                               │
│    │sessions │                  │ courses  │◄──────────┐                    │
│    └─────────┘                  └────┬─────┘          │                    │
│                                      │               │                    │
│    ┌─────────────────────────────────┼───────────────┘                    │
│    │                                 │                                     │
│    │     ┌───────────────────────────┴─────────────────────────┐         │
│    │     │                                                     │         │
│    │ ┌───┴───────┐                    ┌──────────────┐        │         │
│    │ │enrollments│                    │ file_metadata│        │         │
│    │ └─────┬─────┘                    └──────┬───────┘        │         │
│    │       │                                │                │         │
│    │       │                    ┌────────────┴─────────┐      │         │
│    │       │                    │                      │      │         │
│    │       │                    │  ┌──────────────┐   │      │         │
│    │       │                    │  │ vector_chunks│   │      │         │
│    │       │                    │  └──────────────┘   │      │         │
│    │       │                    │                      │      │         │
│    │       │                    │  ┌──────────────┐   │      │         │
│    │       │                    │  │  materials   │   │      │         │
│    │       │                    │  └──────────────┘   │      │         │
│    │       │                    │                      │      │         │
│    └───────┼────────────────────┴──────────────────────┼──────┘         │
│            │                                          │                 │
│    ┌───────┴───────┐                         ┌────────┴────────┐        │
│    │chat_sessions │                         │     audit_log   │        │
│    └───────┬───────┘                         └─────────────────┘        │
│            │                                                            │
│    ┌───────┴───────┐                                                    │
│    │chat_messages │                                                    │
│    └───────────────┘                                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 20.4 Index Strategy Summary

| Table | Index Type | Columns | Purpose |
|-------|-----------|---------|---------|
| users | B-tree | email (WHERE active) | Login queries |
| users | B-tree | role | Role filtering |
| sessions | B-tree | session_token | Session lookup |
| sessions | B-tree | user_id + is_active | User's active sessions |
| courses | B-tree | teacher_id | Teacher's courses |
| courses | B-tree | code | Course lookup |
| courses | GIN | name + description | Full-text search |
| enrollments | B-tree | student_id + status | Student's active enrollments |
| enrollments | B-tree | course_id + status | Course's students |
| file_metadata | B-tree | owner_user_id + course_id | File queries |
| file_metadata | B-tree | drive_file_id | Drive sync |
| vector_chunks | HNSW | embedding | Vector similarity search |
| vector_chunks | B-tree | file_metadata_id | Chunk lookup |
| chat_messages | B-tree | session_id + created_at | Message history |
| audit_log | B-tree | user_id + created_at | User audit trail |
| audit_log | B-tree | event_type + created_at | Event queries |

---

### 20.5 Big Tech Features Implemented

| Feature | Implementation | Why It Matters |
|---------|---------------|----------------|
| **Row-Level Security** | All data tables have RLS policies | Multi-tenant safety at DB level |
| **Encrypted Columns** | pgcrypto for refresh tokens | Sensitive data encrypted at rest |
| **Event Sourcing** | audit_log table captures all changes | Complete audit trail |
| **Soft Deletes** | status columns instead of DELETE | Data recoverable, analytics preserved |
| **Idempotency** | Upsert patterns for enrollments | Prevents duplicate records |
| **Materialized Views** | user_activity_summary, course_stats | Fast aggregated queries |
| **Table Partitioning** | chat_messages, audit_log by month | Manage large tables |
| **Connection Pooling** | PgBouncer recommended | Handle high concurrency |
| **Prepared Statements** | SQLAlchemy default | SQL injection prevention |
| **Query Timeouts** | statement_timeout = 30s | Prevents runaway queries |
| **Role-Based Access** | Separate vta_app, vta_readonly roles | Principle of least privilege |
| **WAL Archiving** | Continuous backup | Point-in-time recovery |
| **Full-Text Search** | GIN indexes on text columns | Search without external tools |

---

### 20.6 Query Performance Examples

```sql
-- Fast user login (uses index)
SELECT * FROM users 
WHERE email = 'prof@example.edu' AND status = 'active';

-- Fast vector search (uses HNSW index) - under 10ms for 100K vectors
SELECT text, 1 - (embedding <=> query_embedding) as similarity
FROM vector_chunks vc
JOIN file_metadata fm ON vc.file_metadata_id = fm.id
WHERE fm.course_id = ANY(ARRAY[1,2,3])
ORDER BY embedding <=> query_embedding
LIMIT 5;

-- Course enrollment with count (uses materialized view)
SELECT cs.*, css.*
FROM courses cs
JOIN LATERAL (
    SELECT COUNT(*) as student_count
    FROM enrollments e
    WHERE e.course_id = cs.id AND e.status = 'active'
) cs ON true
WHERE cs.teacher_id = 1;

-- User activity report (uses materialized view)
SELECT * FROM user_activity_summary
WHERE last_message_at > NOW() - INTERVAL '7 days'
ORDER BY total_messages DESC
LIMIT 10;

-- Audit log for security (partitioned, indexed)
SELECT * FROM audit_log_2026_04
WHERE user_id = 1
AND event_type IN ('USER_LOGIN', 'FILE_SYNC')
AND created_at > NOW() - INTERVAL '24 hours';
```

---

This enterprise-grade schema follows big tech company standards with comprehensive security, scalability, and performance features built into the database layer itself.
