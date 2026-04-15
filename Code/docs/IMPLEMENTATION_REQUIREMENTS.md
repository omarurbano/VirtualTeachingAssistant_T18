# Virtual Teaching Assistant - Implementation Requirements

## Project Overview

This document outlines the missing features and implementation requirements for the Virtual Teaching Assistant (VTA) application. The VTA is designed to be an AI-powered teaching assistant where students and teachers can log in, teachers can manage courses and upload materials, and students can interact with an AI assistant that answers questions based on course materials.

---

## Table of Contents

1. [Current Project Status](#current-project-status)
2. [Missing Features](#missing-features)
3. [Feature 1: Google Drive Integration](#feature-1-google-drive-integration)
4. [Feature 2: Live Real-Time Analytics](#feature-2-live-real-time-analytics)
5. [Database Schema Requirements](#database-schema-requirements)
6. [Implementation Priority](#implementation-priority)
7. [Testing Requirements](#testing-requirements)

---

## Current Project Status

### ✅ Implemented Features

| Feature | Status | Details |
|---------|--------|---------|
| **User Authentication** | ✅ Complete | Email/password login with role-based routing (teacher/student) |
| **Course Management** | ✅ Complete | Teachers can create courses with unique enrollment codes |
| **Course Enrollment** | ✅ Complete | Students can join courses using enrollment codes |
| **Document Upload** | ✅ Complete | PDF, DOCX, TXT file uploads with embedding |
| **VTA Chat Interface** | ✅ Complete | RAG-powered Q&A with citations |
| **Multimodal Processing** | ✅ Complete | Images, tables, audio extraction from PDFs |
| **Role-Based UI** | ✅ Complete | Separate teacher dashboard and student home pages |

### ❌ Missing Features

| Feature | Priority | Status |
|---------|----------|--------|
| **Google Drive Integration** | HIGH | Not implemented - UI placeholder only |
| **Live Analytics** | HIGH | Hardcoded mock data in UI |
| **Course-Contextual VTA** | MEDIUM | No course-scoped document queries |
| **Data Leakage Prevention** | MEDIUM | VTA can answer unrelated questions |

---

## Missing Features

### Feature 1: Google Drive Integration

#### Requirement Summary

Teachers should be able to:
1. Link their Google Drive by pasting a URL
2. Select specific folders or files to embed
3. All documents from Google Drive should be **vectorized (embeddings stored-only)**
4. Original documents are NOT stored - only embeddings are kept to save storage
5. Students can query through the VTA using these embedded materials

#### Current Issues

- The `course.html` page has a "Link Google Drive" button (lines 178-191)
- Clicking it shows: `"Drive integration coming soon!"`
- No OAuth flow implemented
- No file listing from Google Drive
- No embedding pipeline for Drive files

#### Implementation Plan

**Phase 1: Google OAuth Setup**
```
1. Set up Google Cloud Project with Drive API enabled
2. Create OAuth 2.0 credentials (Client ID + Secret)
3. Configure redirect URIs
4. Add credentials to .env file
```

**Phase 2: Backend Implementation**
```
1. Create /drive/auth endpoint (OAuth consent URL)
2. Create /drive/callback endpoint (token exchange)
3. Create /drive/files endpoint (list Drive files)
4. Create /drive/sync endpoint (download + vectorize documents)
5. Store embeddings in vector store with course_id metadata
```

**Phase 3: Vectorization Storage**
```
- Download document from Google Drive
- Extract text content
- Generate embeddings
- Store ONLY embeddings (no full document)
- Associate with course_id for scoping
```

**Phase 4: Query Integration**
```
- When student queries VTA, search ONLY their enrolled course's embeddings
- Prevent cross-course data leakage
```

#### Google Drive API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/drive/auth` | GET | Start OAuth flow, return consent URL |
| `/drive/callback` | GET | Handle OAuth callback, store tokens |
| `/drive/files` | GET | List teacher's Drive files |
| `/drive/sync` | POST | Download + vectorize selected files |
| `/drive/synced` | GET | List already synced files |

---

### Feature 2: Live Real-Time Analytics

#### Requirement Summary

The teacher analytics dashboard should show **real live analytics**:
1. Real-time confusion topics (what students are struggling with)
2. Real-time query tracking
3. Actual student engagement metrics
4. At-risk student detection based on actual interactions

#### Current Issues

**The `analytics.html` page is 100% HARDCODED:**

```javascript
// Hardcoded mock data in analytics.html (lines 75-101)
<tr class="heatmap-row" data-topic="Backpropagation">
  <td class="topic-name-cell">Backpropagation</td>
  <td class="q-count-cell">42</td>  // HARDCODED!
  <td><span class="diff-badge diff-high">HIGH</span></td>  // HARDCODED!
</tr>
```

```javascript
// Hardcoded queries (lines 519-532)
const QUERIES = [
  { topic:'Backpropagation',  time:'2025-04-06 15:41', student:'STU_7F2A', ...},
  { topic:'Loss Functions',   time:'2025-04-06 15:29', student:'STU_C3D1', ...},
  // ALL DATA IS HARDCODED
];
```

**Charts are also hardcoded:**
```javascript
// Line 417 - HARDCODED chart data
data: [12, 15, 28, 30, 42],  // Not from database
```

#### Real-Time Analytics Implementation

**Phase 1: Query Tracking Database**
```
1. Create 'queries' table in Supabase
2. Record every student question: question_text, course_id, student_id, timestamp
3. Record VTA response: answer_text, sources_used, confidence
```

**Phase 2: Analytics API**
```
1. GET /api/analytics/<course_id> - Returns live stats
2. GET /api/analytics/<course_id>/confusion - Returns confusing topics
3. GET /api/analytics/<course_id>/queries - Returns real query history
4. GET /api/analytics/<course_id>/students - Returns at-risk students
```

**Phase 3: Topic Analysis**
```
1. Analyze student questions to extract topics
2. Track failed queries (no good answer found)
3. Track repeated questions (confusion indicators)
4. Calculate difficulty scores based on query patterns
```

**Phase 4: At-Risk Detection**
```
1. No session in X days = LOW INTERACTION
2. Repeat same question = Repeated confusion
3. Failed queries > threshold = STRUGGLING
```

---

## Database Schema Requirements

### Existing Supabase Tables

Check `server/db.js` - Database credentials are configured:
```javascript
const supabaseUrl = "https://ehqjplwrrifezdwlsdbk.supabase.co";
const supabaseKey = "sb_publishable_rQZPfUr5fzxlGra3F1drJQ_qOUlx8Jo";
```

### Required New Tables

```sql
-- 1. QUERIES TABLE (Track all student questions)
CREATE TABLE queries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,
  sources_used TEXT[],
  confidence_score FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. COURSE_MATERIALS TABLE (Track vector embeddings)
CREATE TABLE course_materials (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id TEXT NOT NULL,
  source_type TEXT, -- 'upload' or 'google_drive'
  file_name TEXT,
  chunks_count INTEGER,
  embedded_at TIMESTAMP DEFAULT NOW()
);

-- 3. STUDENT_PROGRESS TABLE (Track engagement)
CREATE TABLE student_progress (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id TEXT NOT NULL,
  student_id TEXT NOT NULL,
  total_queries INTEGER DEFAULT 0,
  failed_queries INTEGER DEFAULT 0,
  last_session TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 4. GOOGLE_DRIVE_LINKS TABLE (Track Drive connections)
CREATE TABLE google_drive_links (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id TEXT NOT NULL,
  teacher_id TEXT NOT NULL,
  drive_folder_url TEXT,
  refresh_token TEXT,
  connected_at TIMESTAMP DEFAULT NOW()
);
```

---

## Implementation Priority

### Priority 1: Google Drive Integration

**Steps:**
1. Set up Google Cloud credentials
2. Implement OAuth flow
3. Implement file listing
4. Implement vectorization pipeline
5. Integrate with course context

**Files to Create:**
- `Code/backend/gdrive/oauth.py` - OAuth authentication
- `Code/backend/gdrive/client.py` - Drive API client
- `Code/backend/gdrive/vectorizer.py` - Download & embed

### Priority 2: Live Analytics

**Steps:**
1. Add Supabase query tracking
2. Create analytics API endpoints
3. Replace hardcoded analytics.html with live data
4. Implement topic analysis
5. Implement at-risk detection

**Files to Modify:**
- `Code/backend/app.py` - Add analytics endpoints
- `Code/frontend/instructor/templates/instructor/analytics.html` - Remove hardcoded data

### Priority 3: Course-Contextual VTA

**Steps:**
1. Scope vector store by course_id
2. Filter queries by enrolled courses
3. Prevent cross-course data leakage

---

## Testing Requirements

### Google Drive Testing

1. Teacher can authenticate with Google
2. Teacher can list Drive files
3. Teacher can select files to embed
4. Embeddings are stored correctly
5. VTA answers from embedded content only

### Analytics Testing

1. Student query is recorded in database
2. Analytics dashboard shows real data
3. Confusion topics update in real-time
4. At-risk students are detected correctly

### Data Leakage Testing

1. Student in Course A cannot access Course B materials
2. VTA only answers from enrolled course materials
3. Cross-course queries return null/not found

---

## Environment Variables Required

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5000/drive/callback

# Supabase (already configured)
SUPABASE_URL=https://ehqjplwrrifezdwlsdbk.supabase.co
SUPABASE_KEY=your_anon_key
```

---

## Summary

| Feature | Current State | Required Action |
|---------|-------------|---------------|
| Google Drive | UI only | Full implementation needed |
| Live Analytics | Hardcoded | Replace with Supabase queries |
| Course-Scope VTA | Global scope | Add course_id filtering |
| Data Leakage | None | Add course boundaries |

---

*Document Version: 1.0*
*Created: April 2026*
*Project: CPT_S 421 - Virtual Teaching Assistant*