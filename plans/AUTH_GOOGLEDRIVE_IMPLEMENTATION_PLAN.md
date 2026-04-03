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

#### Should Build (V1.1)

| Feature | Why |
|---------|-----|
| Course-based access control | Students only see their course materials |
| Re-sync detection | Efficient updates when Drive files change |
| Progress indicators during sync | UX for large file syncs |
| Better chunking (semantic) | Better retrieval quality |

#### Can Wait (V2)

| Feature | Why |
|---------|-----|
| Multi-teacher collaboration | Multiple teachers per course |
| Student-uploaded questions | Students add their own notes |
| Quiz generation from materials | Advanced feature |
| Analytics (most-asked topics) | Teacher dashboard |
